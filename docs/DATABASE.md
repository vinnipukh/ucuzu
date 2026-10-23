# SQLite Database

This file owns the database schema, indexes, build pipeline and runtime connection mode. The build command is in [GETTING-STARTED.md](GETTING-STARTED.md); input file formats are in [DATA_CONTRACT.md](DATA_CONTRACT.md).

## Purpose

`data/prices.db` is the read-optimized serving database for the Falcon API. It is generated from the committed `data/` tree by `scripts/build_database.py` and is never committed to Git (`*.db`, `*.db-wal`, `*.db-shm`, `*.db.building*` and `*.db.staging*` are ignored).

If the database file is missing or 0 bytes, `/api/health` still returns 200 with `data.database: "unavailable"`, and every data endpoint returns HTTP 503 with error code `database_unavailable` and message "Database not found; run scripts/build_database.py". The API reads no other data source.

> **Changed 2026-10-17:** the runtime CSV fallback was removed, so a missing database returns 503; previously the API fell back to reading CSVs, which found no files in the committed `data/` layout. See [change history](README.md#change-history).

A database built before the catalog columns existed (`products` without `name_key`, `previous_price`, `price_since`, `is_current` or `is_store_latest`) still serves every other endpoint, but the `/api/catalog/*` routes return HTTP 503 with error code `database_outdated` and message "Database predates the catalog; run scripts/build_database.py". Rebuild the database to fix it.

## Build pipeline

`scripts/build_database.py` options: `--data-dir` (default `data/`), `--db-path` (default `PRICES_DB_PATH`, else `data/prices.db`) and `--workers` (default CPU count − 1, at least 1).

1. **Join split files.** Runs `data_files.join` so files committed as `.partNNN` chunks (none today) are rebuilt first.
2. **Clean up.** Deletes leftovers of a previous crashed build: `<db>.building` and `<db>.staging`, each with `-wal`, `-shm` and `-journal`.
3. **Create the target.** Builds into `<db>.building` with `journal_mode=OFF`, `synchronous=OFF` and a 512 MB page cache, and attaches a scratch database `<db>.staging` (journal off) holding an append-only `obs` table, so staging pages never bloat the served file.
4. **Ingest raw CSVs** in parallel worker processes (see [Raw CSV ingestion](#raw-csv-ingestion)).
5. **Ingest JSON fallback** for retailers that got no raw rows (see [JSON fallback](#json-fallback)).
6. **Write tables.** Inserts `retailers`, `categories` and `products` (with each product's `name_key`, see [Catalog columns](#catalog-columns), and its [product details](#product-details-and-unit-prices)); copies staged observations into `observations`, keeping the **last staged row** per `(product, date)`; then fills each product's first/last date, min/max price, observation count and latest price.
7. **Compute price changes** (printed as "Computing price changes..."). Fills `previous_price`, `price_since`, `is_current` and `is_store_latest` on every product (see [Catalog columns](#catalog-columns)).
8. **Compute unit prices** (printed as "Computing unit prices..." with the number of products that got one). Parses every product title in worker processes and fills `unit_price` and `unit_price_unit` from `latest_price` (see [Product details and unit prices](#product-details-and-unit-prices)).
9. **Indexes, views, statistics.** Creates the [indexes](#indexes) and [views](#views), runs `ANALYZE`, and switches the file to `journal_mode=WAL` (what the read-only API connections expect).
10. **Swap in.** Closes the connection, deletes `<db>.staging`, removes any stale `<db>-wal` and `<db>-shm`, and atomically replaces the target with `os.replace(<db>.building, <db>)`.

On Windows, stop the API before rebuilding: an open database cannot be replaced. On other platforms, restart the API after a rebuild; running workers keep their open connection and 5-minute caches.

Changes to the data layout, file formats, retailer folders or schema must update `scripts/build_database.py` and `tests/test_build_database.py` in the same commit.

### Raw CSV ingestion

Every `*.csv` under `data/raw` is considered.

**Date.** The date comes from the file name, first match wins: `YYYY-MM-DD`, `DD-MM-YYYY` or `YYYYMMDD`, with `-`, `_` or `.` as separators in the first two forms; the year must start with `20` and the date must be valid.

Without a full date, a file stem ending in `<month>-<day>` (one or two digits each, `-` separator: `products10-19.csv`, `products-02-23.csv`, `Clothes3-10.csv`, `sehirhatlari_fares_5-31.csv`) gets the first such date on or after `SCRAPE_START` (2026-02-23), so `3-10` is 2026-03-10 and `1-5` would be 2027-01-05. 2026-02-23 is when the upstream repository InflationResearchStudy was created, and its GitHub history shows no month-day file committed before its name date read as 2026 (checked 2026-10-20 for Kim, Defacto, Antalya, AfeksYapiMarket, Ikea and PublicTransportation). The rule is unambiguous only for scrapes before 2027-02-23: after that a month-day name would be dated a year early, so such scrapers must switch to full dates or the rule must change.

Other files (for example `series.csv`, `cagri_all_products.csv`, or the monthly `health_prices_2026-03.csv`) are skipped. The Health medicine lists are left undated on purpose: they have no day, all eight were uploaded together on 2026-10-16, and the files for 2026-06 to 2026-10 repeat earlier months' prices exactly (06, 07 and 08 equal 03, 09 equals 04, 10 equals 05).

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

**Header aliases.** If a file has none of the domain's name columns (`product-name`, `product_name`, `name`, `Product Name`, `brand`, `District`), the first header matching a name alias is renamed to `name`. If it has none of the domain's price columns (`member_price`, `original_price`, `shown_price`, `product-price`, `product_price`, `price`, `Price`, `median_price`, `Fiyat`), the first header matching a price alias is renamed to `price`. Category and product id work the same way: without one of the domain's category columns (`category`, `Category`, `Ana Kategori`, `Rooms`) the first category alias is renamed to `category`, and without one of its id columns (`Stok Kodu`, `sku`, `product_id`, `UrunID`, `id`, `Kategori ID`) the first id alias is renamed to `product_id`. Headers are compared casefolded with spaces, `_`, `-` and the dotted-İ mark removed. Aliases, in priority order (`NAME_ALIASES` / `PRICE_ALIASES` / `CATEGORY_ALIASES` / `ID_ALIASES`):

- name: `productname`, `name`, `urunadi`, `ürünadı`, `urunismi`, `isim`, `ad`, `urun`, `title`
- price: `price`, `fiyat`, `fiyatfloat`, `pricetl`, `price(tl)`, `saleprice`, `currentprice`, `productcost`, `normalprice`, `regularprice`
- category: `fullcategory`, `categorypath`, `anakategori`, `kategori`, `subcategory`, `topcategory` (A101 `ana_kategori`, Arden/Kale/Marketzade/addax/Altınyıldız `kategori`, GoldenRose `Full Category`, Pazarium `subcategory`)
- product id: `urunid`, `productcode`, `sku`, `productid` (A101/addax `urun_id`, Cagri `product_code`, Macrocenter/GoldenRose `SKU`)

`category_number` / `sub_category_number`, written by many upstream scrapers, are TÜİK codes (`05`, `0511116`), not shop categories, and are not aliased.

Rows are then normalized by `build_product_frame` in `inflation_dashboard/domain/prices.py` (product id, name, category and price coercion). A missing category becomes `Uncategorized`.

**Product details.** `product_details` (same module) also reads five optional columns, matched on the same normalized header against `DETAIL_HEADERS` (first match wins); the column already used as the price is never the regular price:

| Detail | Header spellings | Sent by (2026-10) | Kept when |
|---|---|---|---|
| `brand` | `brand`, `marka`, `markaadi` | A101 `marka`; Macrocenter, Onur, GoldenRose, DR, Nezih, Bershka, Koctas, Nalburadam, Nalburtek, KarekodSigara, MilliGazete `Brand` | not empty |
| `barcode` | `barcode`, `barkod`, `barkodno`, `ean`, `ean13`, `gtin` | A101 `barkod`, addax `barcode` | 8–14 digits |
| `image_url` | `imageurl`, `image`, `resimurl`, `resim`, `img`, `imgurl`, `gorsel`, `gorselurl`, `photourl` | A101 `resim_url`, Arden `resim`, Hapeloglu, Karaca, DR, Nezih, GoldenRose `Image URL` | absolute `http(s)` link |
| `product_url` | `producturl`, `url`, `link`, `urunurl`, `urunlinki`, `productlink` | A101, Flormar, Watsons, Chakra and the Communication plans `url`; Arden `link`; Cagri, Hapeloglu, Loft, Karaca, DR, Nezih, GoldenRose `Product URL` | absolute `http(s)` link |
| `regular_price` | `regularprice`, `normalfiyat`, `originalprice`, `productoriginalcost`, `listprice`, `oldprice`, `eskifiyat` | A101 `normal_fiyat`; Macrocenter, Hapeloglu, Bershka `RegularPrice`; Mudo `Original Price`; DR, Nezih, GoldenRose, Karaca `Product Original Cost`; Communication `list_price` | a positive price |

A product keeps the newest non-empty value of each detail, and the regular price only when it was sent on the product's `last_date`, so a stale undiscounted price never sits beside a newer price.

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

`data/prices_json/*.json` partitions are used **only for retailers with no successfully ingested raw CSV**; a partition whose retailer has raw CSVs is skipped with the message `JSON ignored: <file> (…)`. Every retailer comes from JSON today (`data/raw/` has no CSVs): new scrapes are converted into partitions by `scripts/csv_to_json.py` ([DATA_CONTRACT.md](DATA_CONTRACT.md#partitioned-json-input-dataprices_json)). The retailer comes from the file stem (`retailer_from_stem`): the first `_` becomes ` / ` and later underscores stay in the store name (`Markets_Gurmar` → `Markets / Gurmar`, `Transport_motor_bicyle_car` → `Transport / motor_bicyle_car`), with one alias: `Health_Diagnostic_Surgical_Services` → `Health / Diagnostic&Surgical Services`. `retailer_stem` is the inverse; it rejects labels that cannot round-trip (an `_` in the group, more than one ` / `, or a character Windows forbids in file names).

Each partition maps `product_id` to an object. Only `name` (default: the product id), `category` (default `Uncategorized`), `prices` (`{"YYYY-MM-DD": price}`, `null` prices skipped) and the optional detail fields `brand`, `barcode`, `image_url`, `product_url` and `regular_price` (counted as sent on the product's newest date) are read. Stored fields such as `latest_price`, `min_price` and `max_price` are ignored; the build recomputes them from the observations. Each date becomes one synthetic source row `<file>.json#YYYY-MM-DD`, so the API's newest-N-files (`max_files`) selection still works.

`EpeyKatfg` and `HomeGoods` (top level) come from mirror partitions; `EpeyKatfg`'s raw files have no date in the name. Every other partition was written by `scripts/csv_to_json.py`.

## Schema

Storage is normalized so repeated text is stored once. The schema is defined in `SCHEMA`, `INDEXES` and `VIEWS` in `scripts/build_database.py`.

### Tables

| Table | One row per | Columns |
|---|---|---|
| `retailers` | retailer label | `retailer_key`, `name` (unique) |
| `categories` | category name | `category_key`, `name` (unique) |
| `sources` | ingested file (JSON: one synthetic row per date) | `source_key`, `file_path` (unique; raw CSVs relative to `data/`, e.g. `raw/01_Food/...`; JSON as `<file>.json#YYYY-MM-DD`), `retailer_key`, `date`, `file_size`, `mtime`, `rows_ingested`, `ingested_at` |
| `products` | `(retailer_key, product_id)` (unique) | `product_key`, `retailer_key`, `product_id`, `product_name`, `name_key`, `category_key`, `first_date`, `last_date`, `latest_price`, `min_price`, `max_price`, `observations_count`, `previous_price`, `price_since`, `is_current`, `is_store_latest`, `brand`, `barcode`, `image_url`, `product_url`, `regular_price`, `unit_price`, `unit_price_unit` |
| `observations` | product per day | `product_key`, `date`, `price`, `category_key` (as observed that day), `source_key` |

`observations` is a `WITHOUT ROWID` table with primary key `(product_key, date)`, so a product's full history is one contiguous range read. A product's name and category in `products` come from its latest observation; renamed products keep a single history.

### Catalog columns

These `products` columns serve the price-comparison catalog (`/api/catalog/*`, [FALCON_API_CONTRACT.md §4.11–§4.14](FALCON_API_CONTRACT.md#411-get-apicataloggroups)):

| Column | Meaning |
|---|---|
| `name_key` | `name_key(product_name)` from `inflation_dashboard/domain/catalog.py`: Turkish-aware lowercase (`I` → `ı`, `İ` → `i`), decimal commas as dots, punctuation as spaces, number and unit joined (`500 g` → `500g`), whitespace collapsed. Products of different retailers with the same `name_key` are one catalog item. |
| `previous_price` | Price on the newest day whose price differs from `latest_price`; `NULL` if the price never changed. |
| `price_since` | First day of the current price (the day after `previous_price` was last seen), or `first_date` if the price never changed. |
| `is_current` | `1` when `last_date` is within 7 days of the newest `last_date` of the product's retailer **and** within `CURRENT_WINDOW_DAYS` (45) days of the newest `last_date` in the database; else `0`. Products of retailers that stopped being scraped therefore drop out of the catalog. |
| `is_store_latest` | `1` when `last_date` is the newest `last_date` among the retailer's products with the same `name_key` (the store's latest prices for that item); else `0`. Catalog search counts only these offers, so an older, cheaper product of the same store does not set an item's price. |

> **Changed 2026-10-18:** `name_key`, `previous_price`, `price_since` and `is_current` were added, and on 2026-10-20 `is_store_latest`; a database built before either change returns 503 `database_outdated` on `/api/catalog/*` until it is rebuilt; previously `products` had none of these columns. See [change history](README.md#change-history).

### Product details and unit prices

| Column | Meaning |
|---|---|
| `brand`, `barcode`, `image_url`, `product_url` | Newest non-empty value the scraper sent ([Raw CSV ingestion](#raw-csv-ingestion), "Product details"); `NULL` for stores that send none. |
| `regular_price` | The undiscounted price sent on `last_date`, else `NULL`. |
| `unit_price` | `latest_price` divided by the package contents parsed from `product_name`; `NULL` when the title has no contents size, the size is a capacity or only dimensions, or `latest_price` is not positive. |
| `unit_price_unit` | Unit of `unit_price`: `ml` or `g` (to be shown as TL/L and TL/kg), `adet` (per piece), `yikama` (per wash), `m` or `m2`. |

Titles are parsed by `parse` in `inflation_dashboard/domain/product_attributes.py` (rules in its module docstring, examples in `tests/test_product_attributes.py`):

- **Size:** a number and a unit (`ml`, `cl`, `l`/`lt`/`litre`, `cc`, `g`/`gr`, `kg`, `m`, `m2`, or a counted unit such as `adet`, `tablet`, `kapsül`, `rulo`, `yaprak`). In ml, g and pieces `1.440` and `1,850` are thousands; `800 + 250 g` and `120 g/115 g` are summed; `1/2 kg` is 500 g. With several sizes the last weight or volume wins. Products sold by the kilogram (`Domates Kg`) are 1 kg.
- **Multipacks:** `6x200 ml`, `200 ml x 6` and a count after the size (`200 ml 6'lı`, `330 ml 24'lü`) multiply the size; the unit price is per ml or g of the whole package. A count before the size (`20'li 30 g` tea bags), or above 48 after it (`1 kg 405'li` sugar cubes), is the number of pieces inside and the size is the total.
- **Counted goods:** a count with no size is the size in pieces (`Yumurta 30'lu`, diapers `52'li`), so the unit price is per piece. A title saying only `1 Adet` is one piece.
- **Detergents:** a wash count (`50 Yıkama`) gives the price per wash, even when a volume is also given.
- **Not contents:** weight or age ranges (`7-14 Kg` diapers, `0-6 Ay`), weight classes (`Çipura 400/600 Kg`), dimensions (`50x70`, `160 mm`), technical values (W, V, GB, mAh, mg …) and lumens on lamps (`Ampül 8 W 720 L`) become attributes, never sizes. Capacities (`180 Kg Kapasiteli`, a fridge's `451 Lt`, the litres of a pot, storage box or bin bag) get no unit price, unless the title is a consumable for an appliance (`Bulaşık Makinesi Parlatıcısı 750 ml`, dishwasher tablets).
- **Scraper typos:** a contents size of 100 kg or 100 L or more is read as g or ml (`Yoğurt 1750 kg`), and one below 1 ml as litres (`Su 0.75 ml`).

> **Changed 2026-10-23:** these seven columns were added; previously `products` had no details or unit prices. The API does not read them yet, so older databases keep working. See [change history](README.md#change-history).

### Indexes

| Index | Columns |
|---|---|
| `idx_products_retailer_name` | `products(retailer_key, product_name)` |
| `idx_products_name` | `products(product_name)` |
| `idx_products_product_id` | `products(product_id)` |
| `idx_products_name_key` | `products(name_key)` |
| `idx_sources_retailer_date` | `sources(retailer_key, date)` |

The unique constraints add automatic indexes on `retailers.name`, `categories.name`, `sources.file_path` and `products(retailer_key, product_id)`.

### Views

The price adapter (`sqlite_price_repository.py`) queries only these read-only views; the catalog adapter (`sqlite_catalog_repository.py`) reads the `retailers`, `categories`, `products` and `observations` tables directly:

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
