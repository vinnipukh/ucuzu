# Data Contract

This file owns the `data/` layout and the input file formats. How the build turns these files into SQLite is in [DATABASE.md](DATABASE.md).

## Ownership

| Artifact | Producer (data repository) | Path here | Consumer |
|---|---|---|---|
| Retailer price histories (one JSON per retailer) | Upstream scraper CSVs (`InflationItems/Datas/`) converted by `scripts/csv_to_json.py`; a few partitions from the mirror's `InflationItems/prices_json/` | `data/prices_json/` | `scripts/build_database.py` (every retailer today) |
| Scraper reference files (URL lists, notes, caches; no price CSVs since 2026-10-20) | Scrapers, `InflationItems/Datas/`; `EpeyKatfg/` from the mirror | `data/raw/` | none today; `scripts/build_database.py` still reads any dated CSV placed here |
| Generated inflation CSVs | Inflation calculators, `Inflations/Datas/` | `data/inflation/` | `/api/epeykatfg/monthly-inflation` (`EpeyKatfg/monthly_inflation.csv`) |
| SQLite serving database | `scripts/build_database.py` in this repository | `data/prices.db` (never committed) | Falcon WSGI API |

The data repository is `vinnipukh/inflationstudymirror` (mirror) with upstream `urazkagangunes/InflationResearchStudy`. When both have a file at the same path, the mirror's copy wins (upstream renamed CSV headers such as `product-name,product_price` → `product_name,price`; both spellings are accepted).

The SQLite file is a serving artifact built from `data/`, not a source of truth. The API never reads `data/raw` or `data/prices_json` at runtime; `scripts/build_database.py` is the only reader of those folders.

> **Changed 2026-10-17:** `data/raw` is no longer read at runtime; previously the API's CSV fallback could read it when the database was missing. See [change history](README.md#change-history).

## Rules for committed data

- `data/raw/`, `data/prices_json/` and `data/inflation/` are committed. `*.db`, `*.db-wal`, `*.db-shm` and build scratch files are never committed. `scripts/build_database.py` must always rebuild `data/prices.db` from the committed data alone.
- No committed file may exceed 85 MB (see [Large files](#large-files-scriptsdata_filespy)).
- Large data imports are pushed in batches of about 500 MB, so no single push approaches GitHub's 2 GB limit.
- Windows cannot create file names containing `\ : * ? " < > |`; such upstream paths are imported with `\` treated as a folder separator and the other characters replaced by `_`.
- `.gitattributes` stores everything under `data/` byte-for-byte (`-text -diff`): no line-ending conversion.
- **New prices are committed as JSON, not CSV.** `scripts/csv_to_json.py` merges upstream scraper CSVs into `data/prices_json/<Group>_<Store>.json` ([SETUP.md](SETUP.md#43-convert-new-prices-into-json)). Since 2026-10-20 every retailer's prices come from JSON: converting a retailer deletes its ingested CSVs. The CSVs the build could not use (undated, empty, unreadable or without a price column, and the mirror's `EpeyKatfg/series.csv`) were deleted on 2026-10-20, so `data/raw/` has no CSVs; git history still has them.
- **Dropped stores** are deliberately left out of this repository even though upstream still has them. `csv_to_json.py` skips their prices (`DROPPED_RETAILERS`); delete their inflation files again after copying `Inflations/Datas` ([SETUP.md](SETUP.md#43-convert-new-prices-into-json)):

  | Store | Reason |
  |---|---|
  | `Communication / Xiaomi` | Scraping stopped in May 2026. |
  | `Communication / Teknoraks` (also `data/inflation/08_Communication/Teknoraks/`) | Scraping stopped in May 2026, and the file names have no year (`technologyProducts5-10-.csv`), so the build skipped them. |
  | `Technology` (`data/prices_json/Technology.json`, mirror only) | An older copy of Beymen's tech products (May to September 2026), already in `Communication / Beymen`. |

> **Changed 2026-10-20:** prices are committed only as one JSON file per retailer in `data/prices_json/`; previously most retailers' prices were committed as scraper CSVs under `data/raw/`. See [change history](README.md#change-history).

## Large files: `scripts/data_files.py`

Git hosts reject large blobs, so oversized files under `data/` are committed as chunks.

| Command | Behaviour |
|---|---|
| `check` | Lists every file under `data/` larger than **85 MB** (`LIMIT_MB`) that is not itself a part file, asks `git check-ignore` which of them Git would skip, and fails (exit 1) for any that would be committed. If Git cannot be run, it falls back to the managed `.gitignore` block. |
| `split` | Splits each file over 85 MB into **80 MB** (`CHUNK_MB`) chunks named `<name>.part001`, `<name>.part002`, … (three digits). Old `.partNNN` files for that original are deleted first, so re-splitting leaves no stale parts. The original stays on disk and is added to the managed `.gitignore` block. |
| `join` | Rebuilds every original from its parts in order. An original whose size already equals the sum of its parts is left alone. `build_database.py` runs this first. |

All commands accept `--data-dir PATH` (default `data/`).

The managed block in `.gitignore` is delimited by `# >>> split data files (managed by scripts/data_files.py; originals rebuilt by \`join\`)` and `# <<< split data files`; `split` rewrites it, so add other ignore rules outside it. No file is split today (`data/raw/EpeyKatfg/series.csv` was, until it was deleted on 2026-10-20).

## Raw CSV input (`data/raw/`)

- **Layout:** TÜİK COICOP folders (`01_Food/<store>/…`, `03_Clothing/<store>/…`, `04_Housing/<region>/<city>/…`, …) plus a few non-TÜİK top-level folders such as `EpeyKatfg/`. The folder path determines the retailer label; the rules are in [DATABASE.md](DATABASE.md#raw-csv-ingestion).
- **File name:** must contain a full date (`YYYY-MM-DD`, `DD-MM-YYYY` or `YYYYMMDD`; `-`, `_` or `.` separators) or end in `<month>-<day>` (`products10-19.csv`), which is dated within a year from 2026-02-23 ([DATABASE.md](DATABASE.md#raw-csv-ingestion)). Other files are skipped. Scrapers should write full dates: month-day names become ambiguous from 2027-02-23.
- **Delimiter:** comma, semicolon or tab (whichever is most frequent in the header line).
- **Encoding:** UTF-8 (with or without BOM), falling back to cp1254.
- **Columns:** schemas are scraper-specific. A file needs a price column and, ideally, a product id, name and category column. Accepted spellings are the domain's canonical columns (`inflation_dashboard/domain/prices.py`) plus the header aliases listed in [DATABASE.md](DATABASE.md#raw-csv-ingestion).

## Partitioned JSON input (`data/prices_json/`)

One file per retailer; the file stem gives the label: the first `_` becomes ` / ` and later underscores belong to the store (`Markets_Gurmar.json` → `Markets / Gurmar`, `Education_Open_Education.json` → `Education / Open_Education`). Files written by `scripts/csv_to_json.py` hold one product per line, sorted by product id, so diffs show changed products. Shape:

```json
{
  "product-id": {
    "name": "Product",
    "category": "Category",
    "brand": "Brand",
    "barcode": "8690000000000",
    "image_url": "https://…",
    "product_url": "https://…",
    "regular_price": 120.0,
    "latest_price": 100.0,
    "min_price": 90.0,
    "max_price": 110.0,
    "prices": {
      "2026-01-01": 90.0,
      "2026-01-02": 100.0
    }
  }
}
```

`brand`, `barcode`, `image_url`, `product_url` and `regular_price` (added 2026-10-23, see [change history](README.md#change-history)) are optional and present only for stores whose scrapers send them ([DATABASE.md § Raw CSV ingestion](DATABASE.md#raw-csv-ingestion), "Product details"). The build reads only `name` (defaults to the product id), `category` (defaults to `Uncategorized`), `prices` (`null` prices are skipped) and those optional fields. `latest_price`, `min_price` and `max_price` are ignored and recomputed from the observations. A partition is used only when its retailer has no successfully ingested raw CSV; otherwise the build prints `JSON ignored: <file>`.

`csv_to_json.py` reads CSVs with the build's own parser and keeps its rules, so a database built from the JSON matches one built from the CSVs: the last row for a product and date wins (files in path order), and `name`/`category` come from the product's newest row. One difference: a CSV can give a product a different category on different days, while JSON stores one, so `observations.category_key` of converted retailers is the latest category on every day.

Two more rules apply when merging, both for scrapers that added columns later (A101, addax, Cagri, Macrocenter, GoldenRose and Altınyıldız first wrote only `product_name, price`, then ids and categories):

- **Category:** a product's category is its newest one that is not `Uncategorized`, so a real category is never replaced by the fill-in label.
- **Details:** each optional detail is the newest non-empty value across this repository's CSVs, the existing JSON and `--source` (a stored value counts as sent on the product's newest date; ties go to the higher-priority source). `regular_price` is kept only when it was sent on the product's newest date.
- **Name-keyed history moves onto ids:** rows without an id column are keyed by the product name. Such a product joins the id that was ever scraped with exactly that name; its prices fill dates the id lacks. When several ids share the name (the same garment in several colours, for example), the name-keyed product stays, but loses the dates from the first of those ids' prices on, which the ids already cover. The import prints `N name-keyed products moved to their id`.

## Matching data (`data/matching/`)

Files the title parser and later product matching use; committed so builds stay deterministic.

- `brands.json`: the brand list, one brand per line (`name`, folded `key`, `sources`, `stores`). Generated by `uv run python scripts/build_brand_list.py` from the `brand` fields in `data/prices_json`, the Watsons brand list (the categories of `Cosmetics_Watson.json`), first words that start current titles in 3 or more stores, and the overrides below; the rules are in the script's docstring. Regenerate it after importing new data. Not read by the database build yet.
- `brand_overrides.json`: reviewed corrections, `{"add": [brand names], "remove": [brand keys]}`, applied last. Edit this file, not `brands.json`.

## Generated inflation input (`data/inflation/`)

`/api/epeykatfg/monthly-inflation` serves `data/inflation/EpeyKatfg/monthly_inflation.csv` (override with `EPEYKATFG_MONTHLY_CSV`): a UTF-8 CSV with a header and one row per month. Values in `month`, `prev_month` and `groups` stay strings; other values are converted to numbers when they parse. Per-group columns follow the `n_<code>`, `avg_<code>` and `basic_<code>` naming. The response shape is in [FALCON_API_CONTRACT.md](FALCON_API_CONTRACT.md).

If the file is absent or has no header, the endpoint returns 200 with an empty `data` array.

Other files under `data/inflation/` are committed for reference and are not read by the API.

## Updating the data

The checklist (convert with `csv_to_json.py`, `data_files.py check`/`split`, push batches, rebuild, verify) is in [DEVELOPMENT.md](DEVELOPMENT.md). Step-by-step commands for importing from InflationResearchStudy are in [SETUP.md](SETUP.md#4-take-new-data-from-inflationresearchstudy).

## Troubleshooting

- **Data endpoints return 503 `database_unavailable`:** `data/prices.db` (or `PRICES_DB_PATH`) is missing or empty. Build it with `scripts/build_database.py` (see [GETTING-STARTED.md](GETTING-STARTED.md)).
- **A retailer is missing after a build:** check the build summary's skip counts; the usual causes are an undated file name or an unrecognised price header.
