# Documentation Index

Each topic has one owning document; other files link to it instead of repeating it.

## Start here

- [Project README](../README.md) — pitch, quickstart and links.
- [Getting Started](GETTING-STARTED.md) — install, build-database, run and verify commands.
- [Setup Guide](SETUP.md) — new-machine walkthrough: building the database and converting new scrapes from InflationResearchStudy into the per-retailer JSON files.
- [Architecture](ARCHITECTURE.md) — source layout, layer boundaries, request flow and known issues.
- [Agent rules](../AGENTS.md) — hard rules for coding agents: repository boundary, data rules, change policy.

## API and frontend

- [Falcon API Contract](FALCON_API_CONTRACT.md) — authoritative API reference.
- [API Summary](API.md) — endpoint table, link to the contract and performance notes.
- [User Guide](USER_GUIDE.md) — end-user walkthrough of the ucuzu shop and the `/analiz` dashboard.
- [Frontend README](../frontend/README.md) — frontend-only state, environment and source layout.

## Data and configuration

- [Data Contract](DATA_CONTRACT.md) — `data/` layout and file formats ([data/README.md](../data/README.md) is a short pointer).
- [Database](DATABASE.md) — schema, indexes, build pipeline and runtime connection mode.
- [Configuration](CONFIGURATION.md) — every environment variable and launcher flag.

## Contributing

- [Development](DEVELOPMENT.md) — change checklists (API change, schema/data layout change, data update, frontend change).
- [Testing](TESTING.md) — test suite, verification scripts and manual QA.
- [Conventions](CONVENTIONS.md) — pointer; merged into [Architecture](ARCHITECTURE.md#conventions).
- [Concerns](CONCERNS.md) — pointer; merged into [Architecture](ARCHITECTURE.md#operational-notes).

## Research and reports

Dated material: findings reflect the code at the time they were written.

- [Falcon API Optimization Report (2026-09-03)](FALCON-API-OPTIMIZATION-REPORT-2026-09-03.md) — synthesis of the four research notes.
- [Falcon Deployment & Server Tuning Research](FALCON-DEPLOYMENT-TUNING-RESEARCH.md) — WSGI server choice and tuning.
- [research/research-notes-falcon-framework-optimization.md](research/research-notes-falcon-framework-optimization.md) — Falcon request path, middleware, routing and media handling.
- [research/research-notes-profiling-db-caching-falcon.md](research/research-notes-profiling-db-caching-falcon.md) — profiling, SQLite and response caching.
- [research/falcon-benchmarks-case-studies.md](research/falcon-benchmarks-case-studies.md) — published Falcon benchmarks and production case studies.
- [benchmarks/](benchmarks/) — raw load-test results (Granian vs Gunicorn, health and mixed workloads).
- [db_benchmark_results.json](db_benchmark_results.json) — raw SQLite connection-strategy benchmark results.

## Work plans

Plans for agent-driven work; they describe intended changes, not current behaviour.

- [../tasks/](../tasks/) — PRDs: `prd-documentation-overhaul.md` (done, except the deferred US-018), `prd-change-history.md` (done) and `prd-cimri-clone.md` (in progress: the cimri-clone roadmap, one session per phase).
- [../scripts/ralph/](../scripts/ralph/CLAUDE.md) — instructions, `prd.json` and progress log for the Ralph agent loop.

## Archive

Historical material; not current setup guidance.

- [archive/SEPARATION.md](archive/SEPARATION.md) — the 2026 extraction of this repository from the monorepo.
- [archive/monorepo/](archive/monorepo/README.md) — original monorepo documentation.
- [archive/planning/](archive/planning/README.md) — Streamlit-era planning, phases and roadmap.
- [archive/static-inflation-report.html](archive/static-inflation-report.html) — early static inflation report page.

## Change history

What changed in behaviour and documentation, newest first, so a difference from older code can be checked against an intended change. Each entry names its commit; API changes per contract version are also in [FALCON_API_CONTRACT.md §9](FALCON_API_CONTRACT.md#9-changes).

### 2026-10-23 — product details, title parser and unit prices (cimri clone phase 1)

**Breaking / behaviour changes**

- The build, `build_product_frame` and `scripts/csv_to_json.py` keep five optional product details scrapers send: `brand`, `barcode`, `image_url`, `product_url` and `regular_price` (A101, Macrocenter, Hapeloglu, Arden, Cagri, GoldenRose, DR, Nezih, Karaca and 50 more). They are new optional fields in `data/prices_json` and new `products` columns; the newest non-empty value wins, and the regular price only when it was sent on the product's newest date ([DATABASE.md § Raw CSV ingestion](DATABASE.md#raw-csv-ingestion), [DATA_CONTRACT.md § Partitioned JSON input](DATA_CONTRACT.md#partitioned-json-input-dataprices_json)). In the rebuilt database 64,567 products have a brand, 11,407 a barcode, 68,541 an image, 146,137 a store link and 66,454 a regular price. The API does not return them yet.
- New title parser `inflation_dashboard/domain/product_attributes.py` (size, multipack, pieces, attributes, model codes, capacity vs contents) and new `products.unit_price` / `unit_price_unit`, computed by the build from `latest_price`: TL per ml, g, piece, wash, m or m² ([DATABASE.md § Product details and unit prices](DATABASE.md#product-details-and-unit-prices)). The parser finds a size in 87.2% of current Markets titles (89.8% without Tarım Kredi, whose titles are cut off); 312,549 products (64,740 current Markets offers) have a unit price.
- New `data/matching/brands.json` (4,139 brands), built by `scripts/build_brand_list.py` from the retailers' brand columns, the Watsons brand list and first words of titles sold in 3+ stores, with reviewed corrections in `data/matching/brand_overrides.json`; regenerate it after each import ([DATA_CONTRACT.md § Matching data](DATA_CONTRACT.md#matching-data-datamatching), [SETUP.md § 4.5](SETUP.md#45-rebuild-and-check)).
- The 59 retailers that send details were re-imported from InflationResearchStudy `7d6b8e4` (312,088 new prices). This also applied the 2026-10-23 id and category aliases to retailers not re-imported then: Gurmar, Hapeloglu, Karaca, Koctas, Nezih, DR, Chakra, Nalburcuk, Nalburadam, yapimaks, TasciYapiMarket, Huawei, Samsung, PozitifTeknoloji, HanCivata and others are now keyed by the store's own id, so their `product_id` values in the API change, and name-keyed duplicates of id-keyed products were merged (products 980,699 → 953,201).

### 2026-10-23 — categories and product ids from more scrapers

**Breaking / behaviour changes**

- The build and `scripts/csv_to_json.py` now read category and product-id columns under more spellings (`ana_kategori`, `kategori`, `Full Category`, `subcategory`; `urun_id`, `product_code`, `SKU`) and the name column `urun`. A101, Arden, Kale, Marketzade, Cagri, Macrocenter, addax, GoldenRose, Pazarium and Altınyıldız were re-imported from InflationResearchStudy `7d6b8e4`: their products get real categories instead of `Uncategorized` (except Marketzade, whose scraper writes none), and products of A101, addax, Cagri, Macrocenter, GoldenRose and Altınyıldız are keyed by the store's own id, so their `product_id` values in the API change ([DATABASE.md § Raw CSV ingestion](DATABASE.md#raw-csv-ingestion), [DATA_CONTRACT.md § Partitioned JSON input](DATA_CONTRACT.md#partitioned-json-input-dataprices_json)).
- When merging, a real category beats `Uncategorized`, and name-keyed history from before a scraper wrote ids moves onto those ids; same-day prices that were stored under both are no longer counted twice (about 4,600 for A101).

### 2026-10-20 — per-store prices and JSON price data

**Breaking / behaviour changes**

- Databases built before `0707a5c` lack `products.is_store_latest` and return 503 `database_outdated` on `/api/catalog/*` until they are rebuilt with `uv run python scripts/build_database.py`; catalog search now counts only each store's latest offers for an item (`0707a5c`; [DATABASE.md § Catalog columns](DATABASE.md#catalog-columns), [contract §4.12](FALCON_API_CONTRACT.md#412-get-apicatalogsearch)).
- `/api/catalog/item` returns one offer per store (its cheapest on the store's newest date) with the store's other products in `other_offers`, which `summary` and `lowest_ever` ignore, and the product page lists those other offers under each store row (`0707a5c`; [contract §4.13](FALCON_API_CONTRACT.md#413-get-apicatalogitem), [USER_GUIDE.md § Price comparison shop](USER_GUIDE.md#price-comparison-shop)).
- Every retailer's prices now come from one JSON file per retailer in `data/prices_json/` (`4703400`, `e86d921`), so `/api/history` `source_file` values look like `Markets_Gurmar.json#2026-10-17` instead of `raw/...csv` paths (`09a0772`; [DATA_CONTRACT.md § Partitioned JSON input](DATA_CONTRACT.md#partitioned-json-input-dataprices_json), [contract §4.3](FALCON_API_CONTRACT.md#43-get-apihistory)).
- New `scripts/csv_to_json.py` converts and merges upstream scraper CSVs into those JSON files without overwriting existing prices; JSON file stems split on the first `_` only, and month-day file names such as `products10-19.csv` are dated from 2026-02-23 (`0707a5c`; [SETUP.md § 4](SETUP.md#4-take-new-data-from-inflationresearchstudy), [DATABASE.md § JSON fallback](DATABASE.md#json-fallback)).
- On Windows the API launcher now stays in the foreground as the parent process and stops the server's whole process tree when it exits, instead of returning and leaving Granian workers listening on the port (`f701686`; [GETTING-STARTED.md § 5](GETTING-STARTED.md#5-run-the-api)).
- New inflation reference files from InflationResearchStudy were committed under `data/inflation/` (`bcf4537`; [DATA_CONTRACT.md § Generated inflation input](DATA_CONTRACT.md#generated-inflation-input-datainflation)).

**Removed**

- The raw price CSVs under `data/raw/`, replaced by the JSON files, including the files the build could not use and the mirror's `EpeyKatfg/series.csv` (committed as `.part001`/`.part002`) and `EpeyKatfg/catalog.csv`; `data/raw/` keeps only reference files (`09a0772`; [DATA_CONTRACT.md § Rules for committed data](DATA_CONTRACT.md#rules-for-committed-data)).
- Copying upstream CSVs into `data/raw/` as the import method; new scrapes go through `scripts/csv_to_json.py` (`0707a5c`; [SETUP.md § 4.3](SETUP.md#43-convert-new-prices-into-json)).
- The dropped stores `Communication / Xiaomi` and `Communication / Teknoraks` (raw files `09a0772`, Teknoraks' inflation files `bcf4537`) and the mirror's `Technology.json`, an older copy of Beymen's tech products (`e86d921`) (`DROPPED_RETAILERS`; [DATA_CONTRACT.md § Rules for committed data](DATA_CONTRACT.md#rules-for-committed-data)).

### 2026-10-18 — ucuzu price-comparison shop

**Breaking / behaviour changes**

- Databases built before `f15fb2c` lack the catalog columns `name_key`, `previous_price`, `price_since` and `is_current` (and `idx_products_name_key`) and return 503 `database_outdated` on `/api/catalog/*` until they are rebuilt; the dashboard endpoints keep working (`f15fb2c`; [DATABASE.md § Catalog columns](DATABASE.md#catalog-columns), [contract §2.3](FALCON_API_CONTRACT.md#23-error-codes-and-status)).
- New routes `GET /api/catalog/groups`, `/api/catalog/search`, `/api/catalog/item` and `/api/catalog/deals` serve the shop from `adapters/sqlite_catalog_repository.py` and `domain/catalog.py` (`f15fb2c`; [contract §4.11](FALCON_API_CONTRACT.md#411-get-apicataloggroups)–[§4.14](FALCON_API_CONTRACT.md#414-get-apicatalogdeals), [API.md](API.md#endpoints)).
- The ucuzu shop now lives at `/` (`/ara`, `/urun/[key]`, `/firsatlar`, `/alarmlar`, with price alarms in `localStorage` key `price-alarms`), and **the inflation dashboard moved from `/` to `/analiz`**; the site uses white/blue design tokens and the Inter font (`f15fb2c`; the dashboard file's move to `routes/analiz/` landed in its parent `5cbbe0a`; [USER_GUIDE.md](USER_GUIDE.md), [frontend/README.md § Routes](../frontend/README.md#routes)).

**Documentation-only**

- New [SETUP.md](SETUP.md), a new-machine walkthrough from scraped data to a running site (`f15fb2c`).

### 2026-10-17 — docs overhaul and /api/products

**Breaking / behaviour changes**

- A missing or empty database now returns HTTP 503 `database_unavailable` on every data endpoint, and `/api/health` reports it in `data.database`, because the runtime CSV fallback was removed (`99680ca`; [DATABASE.md § Purpose](DATABASE.md#purpose), [contract §2.3](FALCON_API_CONTRACT.md#23-error-codes-and-status), [§4.1](FALCON_API_CONTRACT.md#41-get-apihealth)).
- The uncapped-history warning now reads `all_history requested; history load is uncapped` instead of `all_history requested; CSV load is uncapped` (`99680ca`; [contract § Warnings](FALCON_API_CONTRACT.md#warnings-metawarnings)).
- Unknown routes, wrong methods, other Falcon errors and unhandled exceptions now return the `{data, meta, errors}` envelope (`not_found`, `method_not_allowed`, `http_error`, `server_error`), and `server_error` always says `Internal server error` instead of the exception text (`7ef73ed`; [contract §2.3](FALCON_API_CONTRACT.md#23-error-codes-and-status)).
- The launcher's `--sqlite-db` now defaults to `PRICES_DB_PATH`, then `data/prices.db`, instead of always overwriting `PRICES_DB_PATH` (`82609c3`; [CONFIGURATION.md § Launcher flags](CONFIGURATION.md#launcher-flags)).
- An empty or unset `VITE_API_BASE_URL` now means same-origin `/api` instead of `http://localhost:8000`, and the sidebar's placeholder reads "same origin (/api)" (`2c0c56a`; [CONFIGURATION.md § Frontend](CONFIGURATION.md#frontend), [frontend/README.md § API URL](../frontend/README.md#api-url)).
- New `GET /api/products` lists product names per retailer; the Product explorer's pickers use it instead of the full `/api/history` (about 580 MB → 4 MB for Markets), product-mode `/api/history` requests only the selected retailer, and `filters._parse_date_param` is now `parse_date_param` (`4a04e27`; [contract §4.7](FALCON_API_CONTRACT.md#47-get-apiproducts), [API.md](API.md#endpoints), [USER_GUIDE.md § 1](USER_GUIDE.md#1-product-price-explorer)).
- The default retailers (`Markets / Gurmar`, `ClothingStores / Vakko`, `HomeGoods`) are defined only in `inflation_dashboard/api/filters.py`; their values did not change (`ccbe59e`; [contract §3](FALCON_API_CONTRACT.md#3-common-filter-parameters)).
- The frontend declares Node.js `>=22.12` in `frontend/package.json` `engines` and pins Node 24 in `frontend/.nvmrc`; the same commit fixed the CI of the time (pytest added, Node 24, the nonexistent `verify_redis_store.py` step dropped, `verify_falcon_api.py` run in its no-database mode) before CI was removed (`907efe4`; [GETTING-STARTED.md § Prerequisites](GETTING-STARTED.md#prerequisites)).
- `.gitignore` also ignores the build's `*.db.staging*` scratch files (`637841c`; [DATABASE.md § Purpose](DATABASE.md#purpose)).

**Removed**

- The launcher flag `--no-sqlite-readonly` and the never-read exports `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS` and `SQLITE_URI`; request connections are always read-only (`e3401ac`; [CONFIGURATION.md § Launcher flags](CONFIGURATION.md#launcher-flags)).
- The runtime CSV reader `inflation_dashboard/adapters/csv_price_repository.py` and its variable `INFLATION_DATA_ROOT`; the SQLite database is the only data source (`99680ca`; [CONFIGURATION.md § API and data variables](CONFIGURATION.md#api-and-data-variables)).
- The unused constant `SUPPORTED_RETAILERS` (`ccbe59e`).
- GitHub Actions CI (`.github/workflows/ci.yml`); there is no CI any more, so the checks run locally (`03423c5`; [TESTING.md § No continuous integration](TESTING.md#no-continuous-integration)).
- `docs/SEPARATION.md` from the top level: it moved to [archive/SEPARATION.md](archive/SEPARATION.md) (`f5d0bbd`).
- The content of `docs/CONVENTIONS.md` and `docs/CONCERNS.md`: it moved to [ARCHITECTURE.md § Conventions](ARCHITECTURE.md#conventions) and [§ Operational notes](ARCHITECTURE.md#operational-notes), and the old files are pointers (`a4f4ca2`).

**Documentation-only**

- The docs were restructured so each topic has one owning file: this index, [GETTING-STARTED.md](GETTING-STARTED.md) as the only setup page, [API.md](API.md) reduced to a summary, and the other docs corrected against the code (US-001–US-013, `f5d0bbd` … `80bd7dc`, `e1588bf`).
- Docstrings and TSDoc were added to the API layer, domain, application, adapters, scripts and frontend library, with no behaviour change (US-014–US-017, `7292db1`, `e12098f`, `9c13189`, `3aa2ee4`).
- [AGENTS.md](../AGENTS.md) was aligned with GETTING-STARTED and points at the known issues (US-019, `eea8f71`).
- US-018 (Svelte `@component` blocks) was deferred and is not part of this change.
