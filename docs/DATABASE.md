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
4. normalizes scraper-specific headers before parsing: when a file has none of the domain's name/price columns, aliases such as `İsim`/`isim`/`ad`/`UrunAdi`/`title` (name) and `fiyat`/`FiyatFloat`/`price (TL)`/`sale_price`/`Current Price` (price) are mapped onto them (`NAME_ALIASES`/`PRICE_ALIASES` in the script);
5. loads `data/prices_json` partitions only for retailers that have no raw CSVs;
6. writes the normalized tables below (keeping the last row when a product appears twice on one day), summarizes each product, creates indexes and views, runs `ANALYZE` and atomically replaces the target file.

Options: `--data-dir`, `--db-path` (defaults to `PRICES_DB_PATH` or `data/prices.db`) and `--workers`. Files without a full date in their name, header-only (failed) scrapes, files without a recognised price column, and files that cannot be decoded are skipped and counted by reason in the build summary. Observations are staged in a temporary `<db>.staging` file that is deleted afterwards. On Windows, stop the API before rebuilding: the open database cannot be replaced while it is in use. Changes to the data layout must update this script and `tests/test_build_database.py` together.

## Schema

Storage is normalized so repeated text is stored once; the schema is defined in `SCHEMA`, `INDEXES` and `VIEWS` in `scripts/build_database.py`.

### Tables

| Table | One row per | Columns |
|---|---|---|
| `retailers` | retailer label | `retailer_key`, `name` |
| `categories` | category name | `category_key`, `name` |
| `sources` | ingested file (JSON partitions: one synthetic `<partition>.json#YYYY-MM-DD` row per date, preserving `max_files` semantics) | `source_key`, `file_path`, `retailer_key`, `date`, size, mtime, `rows_ingested`, `ingested_at` |
| `products` | `(retailer, product_id)` | `product_key`, `retailer_key`, `product_id`, latest `product_name` and `category_key`, first/last date, latest/min/max price, observation count |
| `observations` | product per day | `product_key`, `date`, `price`, `category_key` (as observed that day), `source_key` |

`observations` is a `WITHOUT ROWID` table with primary key `(product_key, date)`, so a product's full history is one contiguous range read. A product's name and category in `products` are the values from its latest observation; renamed products keep a single history.

### Views (read-only API shapes)

| View | Shape |
|---|---|
| `price_observations` | `date, retailer, product_id, product_name, category, price, source_file` |
| `product_prices` | product summary plus `price_history` JSON (`{"YYYY-MM-DD": price}`), computed only for the rows selected |
| `ingested_files` | `file_path, retailer, date, file_size, mtime, rows_ingested, ingested_at` |

API adapters query these views; they must not write to them.

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
