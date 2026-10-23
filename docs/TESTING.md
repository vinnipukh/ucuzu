# Testing and Verification

This file owns the test suite, verification scripts and manual QA. Installing dependencies and the everyday commands (`uv run pytest`, `verify_falcon_api.py`, `npm run check`) are in [GETTING-STARTED.md](GETTING-STARTED.md).

## Unit tests (`uv run pytest`)

No database, server or network needed; the suite runs in a few seconds.

| File | Covers |
|---|---|
| `tests/test_prices.py` | `inflation_dashboard/domain/prices.py`: date parsing, price coercion, column detection, product frames, product details (brand, barcode, URLs, regular price) |
| `tests/test_price_cleaning.py` | `inflation_dashboard/domain/price_cleaning.py`: the 999 family, references, placeholder and dotted-thousands decisions with sampled real cases |
| `tests/test_product_attributes.py` | `inflation_dashboard/domain/product_attributes.py` with real titles: sizes, Turkish thousands separators, multipacks and piece counts, counted goods, washes, capacities, dimensions, lumens, weight ranges, unit typos, attributes, brands, must-not-merge pairs, unit prices |
| `tests/test_build_brand_list.py` | `scripts/build_brand_list.py`: brands from retailer columns (only when a title starts with them), the Watsons list, current titles in 3+ stores (generic and old words excluded), overrides; output round-trip |
| `tests/test_use_cases.py` | `inflation_dashboard/application/use_cases.py`: history, averages, movers, coverage calculations |
| `tests/test_build_database.py` | `scripts/build_database.py` (file-name dates, retailer labels, header aliases, small end-to-end builds, day deduplication, catalog columns, product details and unit prices, price clean-up counts and the merged duplicate stores, permanent item/family IDs from `ids.json` with provisional new ones, pack options, `overrides.json` merge/split) and `scripts/data_files.py` split/join; `scripts/assign_ids.py` appending new IDs |
| `tests/test_matching.py` | `inflation_dashboard/domain/matching.py`: same-product spellings share a match key, cimri's must-not-merge pairs differ, multipacks share the single item's key, family keys drop the size, overrides (split, merge, cycles), `assign_ids` numbering |
| `tests/test_csv_to_json.py` | `scripts/csv_to_json.py`: converted JSON builds the same database as the CSVs, `--source` adds new prices without overwriting and folds in remaining raw CSVs, name-keyed history moves onto store ids (and is trimmed where several ids share a name), a real category beats `Uncategorized`, the newest product details are kept (regular price only from the newest date), `--dry-run` changes nothing, unknown retailers are an error; `retailer_stem` round-trip and rejected labels |
| `tests/test_run_falcon_server.py` | Launcher database path precedence: `--sqlite-db` > `PRICES_DB_PATH` > `data/prices.db` |
| `tests/test_api.py` | Falcon `TestClient`: 503 `database_unavailable` (missing or empty database) on data endpoints and `/api/health` reporting it; 404 `not_found` and 405 `method_not_allowed` envelopes; 500 `server_error` with a fixed message and no exception text; CORS header on error responses; `/api/products` grouping, date window and 400s against a tiny database built with `build_database.build` |
| `tests/test_catalog.py` | `inflation_dashboard/domain/catalog.py` (`name_key`, `search_terms`, `split_retailer`); the build's `name_key`, `previous_price`, `price_since` and `is_current` columns; `/api/catalog/*` against a tiny built database: cross-store search, stale offers excluded, bad `sort` (400), item offers and history by item ID, one offer per store (its cheapest on the store's newest date, never an unpriced one), unknown item (404) and missing/invalid `id` (400), pack options with per-package prices, family search, deals and groups, case prices never ranked cheapest nor listed as deals, and 503 `database_outdated` on a database without the catalog columns |

`tests/conftest.py` provides small in-memory history fixtures.

## API verification (`scripts/verify_falcon_api.py`)

Runs in-process with Falcon's `TestClient` (no port). It checks:

- import boundaries: no Streamlit/Plotly in `api/`, no `sqlite3`/Redis/ORMs in `api/`, no Falcon in `domain/`, `application/`, `adapters/`; `/api/health` does not load inventory or history;
- that all fourteen routes are registered and the response-key tokens exist in `resources.py`;
- endpoint smoke tests, depending on the database:
  - **with a built database:** every data endpoint returns a JSON-native envelope with the expected keys, plus product search, monthly inflation, an unknown product name in `/api/history` (200 with an empty summary), an unknown retailer (400 `invalid_filter`) and the catalog routes (groups, a search, the first hit's item, deals, and a bad `sort` returning 400);
  - **without a database:** inventory, history, `/api/products`, product search, product detail and catalog search return 503 `database_unavailable`, and the monthly inflation endpoint still works.

## Frontend

In `frontend/`: `npm run check` (svelte-check) must finish with **0 errors and 0 warnings**; `npm run build` must produce `frontend/build/`. There are no frontend unit tests.

## No continuous integration

The repository has no CI: nothing runs on push or pull request. Run the checks locally before pushing:

1. `uv run pytest`
2. `uv run python scripts/verify_falcon_api.py` (with a built database; with `PRICES_DB_PATH` pointing at a missing file it runs the no-database checks)
3. `npm run check` and `npm run build` in `frontend/`

## Database scripts (need a built database)

These use `PRICES_DB_PATH` or the default `data/prices.db`.

```bash
uv run python scripts/test_sqlite_adapter.py
uv run python scripts/test_new_endpoints.py
uv run python scripts/benchmark_db_queries.py --mode compare
```

- `test_sqlite_adapter.py` times every adapter function (inventory, history with and without a file cap, product detail, averages, movers, coverage) and prints a table; about a minute.
- `test_new_endpoints.py` prints the responses of product search, product detail, an unknown product (404), a missing lookup key (400) and the monthly inflation endpoint.
- `benchmark_db_queries.py` compares SQLite connection strategies under concurrent readers (`--mode compare|scale|all`, `--concurrency`, `--requests`, `--db-path`, `--json-out`). Earlier results are in `docs/db_benchmark_results.json`.

## Load testing

```bash
uv run python scripts/benchmark_falcon_api.py
uv run python scripts/benchmark_concurrent_api.py --concurrency 100
```

- `benchmark_falcon_api.py` times one cold and two warm in-process requests per endpoint.
- `benchmark_concurrent_api.py` sends concurrent HTTP requests to a running server (`--target-url`, default `http://127.0.0.1:8000`), or starts one with `--spawn-server` (`--engine`, `--workers`, `--threads`, `--port`). `--endpoint-suite health|inventory|mixed|all` picks the endpoints; `--output-json` saves results. Earlier results are in `docs/benchmarks/`.

Run load tests against a disposable copy of the database, not one that is being rebuilt or serving users.

## Manual end-to-end check

Build the database and start the API and the frontend ([GETTING-STARTED.md](GETTING-STARTED.md)).

Shop (`/`):

1. The home page shows the deal rail, a popular-products rail per category and the popular stores.
2. Search from the header (try `süt` and `SÜT 1 L`): results match; the category and store filters, sort and paging change the URL; the back button restores the previous search.
3. Open a product: one offer per store, cheapest first with the cheapest highlighted (a store's other listings open under "<store> için N seçenek daha"), the price-history chart switches between 1 month, 3 months and all, and stale offers sit under "Güncel olmayan … fiyat".
4. Set a price alarm above the current price: the header's alarm count goes up and `/alarmlar` marks it **Hedefe ulaştı**. Reload: the alarm is still there. Remove it.
5. `/firsatlar`: the category chips and the minimum-drop and period selects reload the list.
6. At phone width (about 390 px) no page scrolls sideways.

Dashboard (`/analiz`):

1. Open `/analiz`.
2. The header shows **API connected**; the sidebar's API settings show the inventory file count and dates.
3. On a first visit (or after clearing site data) the **Category** is **Markets** and "Retailers to load" lists the Markets retailers. Choose another category, reload the page, and check it is remembered.
4. "Load all files in date range" is on; turning it off enables the file-cap slider (default 45).
5. Open all five views; change dates, retailers, aggregation, mover scope and count; search with Turkish characters and a typo.
6. Toggle the theme and reload: the choice is remembered.
7. Stop the API and change a filter: the view shows a network error. (The header status only updates when the API is checked: on page load, on Apply, or with its retry button.) Restart the API: the next filter change loads data again without a page reload.
8. Point the API at a missing database (`--sqlite-db missing.db`): the dashboard shows "Database not found; run scripts/build_database.py".
9. Point the API at a database built before the catalog columns existed: the dashboard still works and the shop pages show a `database_outdated` error.
