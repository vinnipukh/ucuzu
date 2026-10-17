# SQLite Database

## Purpose

`data/prices.db` is the optimized, read-optimized serving database for the Falcon API. It is generated from the committed `data/` tree and is never committed to Git.

## Build (canonical)

```bash
uv run python scripts/build_database.py
```

`scripts/build_database.py` is the committed, always-working way to recreate the database:

1. rejoins files committed as `.partNNN` chunks (`scripts/data_files.py join`);
2. ingests every CSV under `data/raw` whose file name carries a date (`YYYY-MM-DD`, `DD-MM-YYYY`, `DD.MM.YYYY`, `YYYYMMDD`, with `-`, `_` or `.`), in parallel;
3. labels retailers from their TÜİK folder: `01_Food/<store>` → `Markets / <store>`, `03_Clothing` → `ClothingStores`, `04_Housing/…/<city>` → `HousesRent / <city>`, `06_Health` → `Health`, and `ConstructionSuppliesMarkets`, `HomeGoods` and `Cosmetics` sub-folders keep their own group name; other groups use the folder name without its number;
4. loads `data/prices_json` partitions only for retailers that have no raw CSVs;
5. rebuilds `product_prices`, creates the API indexes, runs `ANALYZE` and atomically replaces the target file.

Options: `--data-dir`, `--db-path` (defaults to `PRICES_DB_PATH` or `data/prices.db`) and `--workers`. Files without a full date in their name, without a recognised price column, or that cannot be decoded are skipped and counted in the build summary. Changes to the data layout must update this script and `tests/test_build_database.py` together.

The two lower-level builders below remain available for single-source builds.

## Tables

### `product_prices`

One materialized row per `(retailer, product_id)`:

- identity and display fields;
- first/latest/min/max observation dates and prices;
- observation count;
- dense `price_history` JSON used for product detail responses.

Primary key: `(retailer, product_id)`.

### `price_observations`

One normalized row per product/date/retailer observation:

- `date`, `retailer`, `product_id`;
- `product_name`, `category`, `price`;
- `source_file` provenance.

Primary key: `(date, retailer, product_id)`.

### `ingested_files`

The build ledger:

- source path, retailer and date;
- file size and modification time;
- ingested row count and timestamp.

This table supports inventory/coverage diagnostics and the API's bounded newest-file selection.

For JSON input, the builder creates one ledger row per retailer/date using a stable synthetic source key (`<partition>.json#YYYY-MM-DD`). This preserves the API's historical `max_files` semantics even though the input is a sparse partition rather than one CSV per day.

## Build from partitioned JSON

```bash
uv run python scripts/build_sqlite_from_json.py \
  --json-dir data/prices_json \
  --db-path data/prices.db
```

The builder creates all three tables, loads product summaries and observations, records each source partition, creates covering indexes and runs `ANALYZE`.

## Build from raw CSV

```bash
uv run python scripts/migrate_csv_to_sqlite.py \
  --datas-dir data/raw \
  --db-path data/prices.db
```

Use `--force` only when a complete rebuild is intentional.

## Production connection policy

Falcon opens SQLite in read-only mode by default:

- `mode=ro`;
- `PRAGMA query_only = 1`;
- WAL-compatible read concurrency;
- `busy_timeout = 5000`;
- 128 MiB page cache by default;
- 1 GiB maximum memory map by default;
- reusable per-thread connections.

The web process does not ingest scraper data and does not require write access.

## Environment

```dotenv
PRICES_DB_PATH=data/prices.db
SQLITE_BUSY_TIMEOUT=5000
SQLITE_CACHE_SIZE=-128000
SQLITE_MMAP_SIZE=1073741824
```

The launcher also accepts `--sqlite-db PATH` and exports the selected path to worker processes.

## Validation

```bash
uv run python scripts/test_sqlite_adapter.py
uv run python scripts/benchmark_db_queries.py --mode compare
uv run python scripts/verify_falcon_api.py
```

Adapter and benchmark scripts require a populated database. Keep generated database files out of Git and deployment source artifacts; deploy them through storage/versioned release mechanisms instead.
