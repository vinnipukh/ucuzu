# SQLite Database

## Purpose

`data/prices.db` is the optimized, read-optimized serving database for the Falcon API. It is generated from data-repository artifacts and is not committed to Git.

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
  --json-dir /path/to/inflationstudymirror/InflationItems/prices_json \
  --db-path data/prices.db
```

The builder creates all three tables, loads product summaries and observations, records each source partition, creates covering indexes and runs `ANALYZE`.

## Build from raw CSV

```bash
uv run python scripts/migrate_csv_to_sqlite.py \
  --datas-dir /path/to/inflationstudymirror/InflationItems/Datas \
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
