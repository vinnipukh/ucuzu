# API Summary

Short overview of the Falcon REST API in `inflation_dashboard/api/`. **[FALCON_API_CONTRACT.md](FALCON_API_CONTRACT.md) is authoritative** for parameters, validation, response shapes, error codes and caching; this page only summarizes it.

## Envelope

Every response, success or error, is a JSON object `{"data": …, "meta": {…}, "errors": […]}`. `data` holds the payload and is `null` on errors. `meta` reflects the applied filters, row and file counts, and `warnings` on success, or the rejected parameters on error. `errors` is empty on success and holds one `{code, message}` object on failure (400 `invalid_filter`, 404 `not_found`, 405 `method_not_allowed`, 500 `server_error`, 503 `database_unavailable`, and 503 `database_outdated` on `/api/catalog/*` when the database predates the catalog columns).

## Endpoints

All routes are `GET`. "Common filters" are `retailer` (repeatable), `start_date`, `end_date`, `max_files` and `all_history`.

| Method | Path | Purpose | Key parameters |
|---|---|---|---|
| GET | `/api/health` | Liveness probe; reports whether the database file is available | — |
| GET | `/api/inventory` | Retailer list and overall date range | — |
| GET | `/api/history` | Filtered observations, or one product's series with a summary | common filters, `product_name`, `product_retailer` |
| GET | `/api/retailer-averages` | Average or median price per retailer per date | common filters, `aggregation` (`Average`/`Median`) |
| GET | `/api/movers` | Biggest drops from peak and biggest gains | common filters, `scope_retailer`, `limit` (5–30) |
| GET | `/api/coverage` | Observation counts over time and per category | common filters, `category_limit` |
| GET | `/api/products` | Product names per retailer for pickers (used by the Product explorer) | `retailer` (repeatable, required), `start_date`, `end_date` |
| GET | `/api/products/search` | Product autocomplete (not used by the SPA) | `q`, `retailer`, `category`, `limit` (1–100) |
| GET | `/api/product` | One product's summary and full price history | `product_id` or `product_name`, `retailer` |
| GET | `/api/epeykatfg/monthly-inflation` | EpeyKatfg monthly inflation rows from the CSV artifact | — |
| GET | `/api/catalog/groups` | Catalog groups and their stores with current-offer counts (shop navigation) | — |
| GET | `/api/catalog/search` | Search items (products sharing a `name_key`) across stores | `q`, `group`, `store`, `sort` (`relevance`/`price_asc`/`price_desc`/`drop`), `limit` (1–60), `offset` (0–10000) |
| GET | `/api/catalog/item` | One item's latest offer per store (other offers of the store under `other_offers`), each with its price history | `key` (required) |
| GET | `/api/catalog/deals` | Current offers with the largest recent price drops | `group`, `store`, `min_drop` (1–80), `days` (1–365), `limit` (1–60) |

## Performance notes

- **Response cache:** `api/filters.py` caches the pre-serialized `orjson` bytes of each successful response per endpoint and query string for 5 minutes, with a gzip variant (bodies ≥ 1 KB) and a strong ETag. Warm requests skip recomputation and serialization, and `If-None-Match` gets a 304. `scripts/benchmark_falcon_api.py` measures warm latency.
- **History cache:** the four filter endpoints share an in-process cache of the loaded history frame per filter signature (5 minutes, bounded by size), so switching between views with the same filters does not re-query SQLite.
- **Product search:** a substring match (`LIKE '%q%'` on `product_name` or `product_id`) over the `product_prices` view. The leading wildcard means no index can be used, so each uncached search scans the products table; results are cached in the adapter for 5 minutes. The search does not select the view's `price_history` column, so no per-product JSON is built.
- **Product detail:** looks the product up by `product_id`/`product_name` (both indexed) and reads its history as one range of the `observations` primary key.
- **Catalog:** `/api/catalog/*` reads the `products` table through `adapters/sqlite_catalog_repository.py`. Item lookups use `idx_products_name_key`; search is a `LIKE '%term%'` per term on `name_key`, restricted to each store's current, latest offers (`is_current = 1 AND is_store_latest = 1`), so an uncached search scans the current products. The retailer table and the schema check are cached per worker for 5 minutes.
- **Data path:** data endpoints read only from the SQLite adapters (`sqlite_price_repository`, `sqlite_catalog_repository`), over one reusable read-only connection per worker thread. `inflation_dashboard/api/` never imports `sqlite3`.
- **Large payloads:** general-mode `/api/history` can be tens of MB with `all_history=true`; keep the default `max_files` bound where possible.
