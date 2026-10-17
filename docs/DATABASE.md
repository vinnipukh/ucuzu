# SQLite Database

This file owns the database schema, indexes, build pipeline and runtime connection mode. The build command is in [GETTING-STARTED.md](GETTING-STARTED.md); input file formats are in [DATA_CONTRACT.md](DATA_CONTRACT.md).

## Purpose

`data/prices.db` is the read-optimized serving database for the Falcon API. It is generated from the committed `data/` tree by `scripts/build_database.py` and is never committed to Git (`*.db`, `*.db-wal`, `*.db-shm`, `*.db.building*` and `*.db.staging*` are ignored).

If the database file is missing or 0 bytes, `/api/health` still returns 200 with `data.database: "unavailable"`, and every data endpoint returns HTTP 503 with error code `database_unavailable` and message "Database not found; run scripts/build_database.py". The API reads no other data source.

## Build pipeline

`scripts/build_database.py` options: `--data-dir` (default `data/`), `--db-path` (default `PRICES_DB_PATH`, else `data/prices.db`) and `--workers` (default CPU count − 1, at least 1).

1. **Join split files.** Runs `data_files.join` so files committed as `.partNNN` chunks (currently `data/raw/EpeyKatfg/series.csv`) are rebuilt first.
2. **Clean up.** Deletes leftovers of a previous crashed build: `<db>.building` and `<db>.staging`, each with `-wal`, `-shm` and `-journal`.
3. **Create the target.** Builds into `<db>.building` with `journal_mode=OFF`, `synchronous=OFF` and a 512 MB page cache, and attaches a scratch database `<db>.staging` (journal off) holding an append-only `obs` table, so staging pages never bloat the served file.
4. **Ingest raw CSVs** in parallel worker processes (see [Raw CSV ingestion](#raw-csv-ingestion)).
5. **Ingest JSON fallback** for retailers that got no raw rows (see [JSON fallback](#json-fallback)).
6. **Write tables.** Inserts `retailers`, `categories` and `products`; copies staged observations into `observations`, keeping the **last staged row** per `(product, date)`; then fills each product's first/last date, min/max price, observation count and latest price.
7. **Indexes, views, statistics.** Creates the [indexes](#indexes) and [views](#views), runs `ANALYZE`, and switches the file to `journal_mode=WAL` (what the read-only API connections expect).
8. **Swap in.** Closes the connection, deletes `<db>.staging`, removes any stale `<db>-wal` and `<db>-shm`, and atomically replaces the target with `os.replace(<db>.building, <db>)`.

On Windows, stop the API before rebuilding: an open database cannot be replaced. On other platforms, restart the API after a rebuild; running workers keep their open connection and 5-minute caches.

Changes to the data layout, file formats, retailer folders or schema must update `scripts/build_database.py` and `tests/test_build_database.py` in the same commit.

### Raw CSV ingestion

Every `*.csv` under `data/raw` is considered.

**Date.** The date comes from the file name, first match wins: `YYYY-MM-DD`, `DD-MM-YYYY` or `YYYYMMDD`, with `-`, `_` or `.` as separators in the first two forms; the year must start with `20` and the date must be valid. Files without a full date (for example `technologyProducts5-10-.csv`, `series.csv`) are skipped.

**Retailer label** from the folders between `data/raw` and the file (`raw_retailer_label`):

| Folder path | Label | Example |
|---|---|---|
| no folder (file directly in `data/raw`) | skipped | — |
| top folder is not a TÜİK folder (`NN_name`) | all folder names joined with ` / ` | `EpeyKatfg/…` → `EpeyKatfg` |
| TÜİK folder only, no store sub-folder | mapped group, else the folder name without its number, **underscores kept** | `13_Personal_Care/x.csv` → `Personal_Care` |
| TÜİK folder, then `ConstructionSuppliesMarkets`, `HomeGoods` or `Cosmetics`, then a store | `<that folder> / <store>` | `05_Furnishings/HomeGoods/Ikea` → `HomeGoods / Ikea` |
| `04_Housing/…/<city>` | `HousesRent / <leaf folder>` | `04_Housing/Duzce_Kocaeli_Sakarya/Duzce` → `HousesRent / Duzce` |
| any other TÜİK folder with a store sub-folder | `<group> / <first sub-folder>`; group is mapped, else the folder name without its number with **underscores turned into spaces** | `03_Clothing/Bershka/ProductData` → `ClothingStores / Bershka`; `02_Alcohol_Tobacco/BirGun` → `Alcohol Tobacco / BirGun` |

Mapped groups: `01_Food` → `Markets`, `03_Clothing` → `ClothingStores`, `04_Housing` → `HousesRent`, `06_Health` → `Health`.

**Parsing.** The delimiter is whichever of `;`, `,` or tab occurs most often in the first line. The file is read as UTF-8 (with BOM handling), then cp1254 if that fails; malformed lines are skipped.

**Header aliases.** If a file has none of the domain's name columns (`product-name`, `product_name`, `name`, `Product Name`, `brand`, `District`), the first header matching a name alias is renamed to `name`. If it has none of the domain's price columns (`member_price`, `original_price`, `shown_price`, `product-price`, `product_price`, `price`, `Price`, `median_price`, `Fiyat`), the first header matching a price alias is renamed to `price`. Headers are compared casefolded with spaces, `_`, `-` and the dotted-İ mark removed. Aliases, in priority order (`NAME_ALIASES` / `PRICE_ALIASES`):

- name: `productname`, `name`, `urunadi`, `ürünadı`, `urunismi`, `isim`, `ad`, `title`
- price: `price`, `fiyat`, `fiyatfloat`, `pricetl`, `price(tl)`, `saleprice`, `currentprice`, `productcost`, `normalprice`, `regularprice`

Rows are then normalized by `build_product_frame` in `inflation_dashboard/domain/prices.py` (product id, name, category and price coercion). A missing category becomes `Uncategorized`.

**Skip reasons**, counted and printed in the build summary:

| Reason | Cause |
|---|---|
| `undated or unlabelled` | no date in the file name, or no retailer label |
| `unreadable (<Exception>)` | the file cannot be read or decoded (`ValueError` when neither UTF-8 nor cp1254 works) |
| `empty (header only)` | the CSV has a header but no rows |
| `no price column` | no price column even after aliasing |
| `unparseable (<Exception>)` | `build_product_frame` raised |
| `no usable rows` | parsing succeeded but produced no rows with a price |

### JSON fallback

`data/prices_json/*.json` partitions are used **only for retailers with no successfully ingested raw CSV**. The retailer comes from the file stem: `_` becomes ` / ` (`Markets_Gurmar` → `Markets / Gurmar`), with one alias: `Health_Diagnostic_Surgical_Services` → `Health / Diagnostic&Surgical Services`.

Each partition maps `product_id` to an object. Only `name` (default: the product id), `category` (default `Uncategorized`) and `prices` (`{"YYYY-MM-DD": price}`, `null` prices skipped) are read. Stored fields such as `latest_price`, `min_price` and `max_price` are ignored; the build recomputes them from the observations. Each date becomes one synthetic source row `<file>.json#YYYY-MM-DD`, so the API's newest-N-files (`max_files`) selection still works.

`EpeyKatfg` and `Technology` come only from `prices_json`, because their raw files have no date in the name. Today `HomeGoods` (top level) also comes from JSON.

## Schema

Storage is normalized so repeated text is stored once. The schema is defined in `SCHEMA`, `INDEXES` and `VIEWS` in `scripts/build_database.py`.

### Tables

| Table | One row per | Columns |
|---|---|---|
| `retailers` | retailer label | `retailer_key`, `name` (unique) |
| `categories` | category name | `category_key`, `name` (unique) |
| `sources` | ingested file (JSON: one synthetic row per date) | `source_key`, `file_path` (unique; raw CSVs relative to `data/`, e.g. `raw/01_Food/...`; JSON as `<file>.json#YYYY-MM-DD`), `retailer_key`, `date`, `file_size`, `mtime`, `rows_ingested`, `ingested_at` |
| `products` | `(retailer_key, product_id)` (unique) | `product_key`, `retailer_key`, `product_id`, `product_name`, `category_key`, `first_date`, `last_date`, `latest_price`, `min_price`, `max_price`, `observations_count` |
| `observations` | product per day | `product_key`, `date`, `price`, `category_key` (as observed that day), `source_key` |

`observations` is a `WITHOUT ROWID` table with primary key `(product_key, date)`, so a product's full history is one contiguous range read. A product's name and category in `products` come from its latest observation; renamed products keep a single history.

### Indexes

| Index | Columns |
|---|---|
| `idx_products_retailer_name` | `products(retailer_key, product_name)` |
| `idx_products_name` | `products(product_name)` |
| `idx_products_product_id` | `products(product_id)` |
| `idx_sources_retailer_date` | `sources(retailer_key, date)` |

The unique constraints add automatic indexes on `retailers.name`, `categories.name`, `sources.file_path` and `products(retailer_key, product_id)`.

### Views

The API adapter queries only these read-only views:

| View | Shape |
|---|---|
| `price_observations` | `date, retailer, product_id, product_name, category, price, source_file` |
| `product_prices` | product summary plus `price_history` JSON (`{"YYYY-MM-DD": price}`), computed only for the rows selected |
| `ingested_files` | `file_path, retailer, date, file_size, mtime, rows_ingested, ingested_at` |

## Runtime connection mode

**Launcher, once at startup.** `scripts/run_falcon_server.py` opens the database **read-write** once: if `journal_mode` is not already `wal` it sets `journal_mode=WAL`, then closes. A freshly built database is already in WAL mode, so normally nothing is written.

**Request connections.** `inflation_dashboard/adapters/sqlite_price_repository.py` opens `file:<path>?mode=ro` and applies:

- `busy_timeout` = `SQLITE_BUSY_TIMEOUT` (default 5000 ms);
- `cache_size` = `SQLITE_CACHE_SIZE` (default −128000, i.e. 128 MiB);
- `mmap_size` = `SQLITE_MMAP_SIZE` (default 1 GiB);
- `synchronous = NORMAL`, `temp_store = MEMORY`, `query_only = 1`.

Each worker thread keeps one reusable read-only connection for its lifetime. WAL readers open the `-wal`/`-shm` files next to the database, so the API process needs access to that directory. Variables are described in [CONFIGURATION.md](CONFIGURATION.md).

## Validation

Validation scripts (`scripts/test_sqlite_adapter.py`, `scripts/benchmark_db_queries.py`, `scripts/verify_falcon_api.py`) are described in [TESTING.md](TESTING.md). The adapter and benchmark scripts need a built database.
