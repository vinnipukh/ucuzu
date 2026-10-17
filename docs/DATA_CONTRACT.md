# Data Contract

This file owns the `data/` layout and the input file formats. How the build turns these files into SQLite is in [DATABASE.md](DATABASE.md).

## Ownership

| Artifact | Producer (data repository) | Path here | Consumer |
|---|---|---|---|
| Raw retailer CSVs | Scrapers, `InflationItems/Datas/` | `data/raw/` | `scripts/build_database.py` only |
| Partitioned JSON histories | Scraper/ETL code, `InflationItems/prices_json/` | `data/prices_json/` | `scripts/build_database.py` (retailers without raw CSVs) |
| Generated inflation CSVs | Inflation calculators, `Inflations/Datas/` | `data/inflation/` | `/api/epeykatfg/monthly-inflation` (`EpeyKatfg/monthly_inflation.csv`) |
| SQLite serving database | `scripts/build_database.py` in this repository | `data/prices.db` (never committed) | Falcon WSGI API |

The data repository is `vinnipukh/inflationstudymirror` (mirror) with upstream `urazkagangunes/InflationResearchStudy`. When both have a file at the same path, the mirror's copy wins (upstream renamed CSV headers such as `product-name,product_price` → `product_name,price`; both spellings are accepted).

The SQLite file is a serving artifact built from `data/`, not a source of truth. The API never reads `data/raw` or `data/prices_json` at runtime; `scripts/build_database.py` is the only reader of those folders.

## Rules for committed data

- `data/raw/`, `data/prices_json/` and `data/inflation/` are committed. `*.db`, `*.db-wal`, `*.db-shm` and build scratch files are never committed. `scripts/build_database.py` must always rebuild `data/prices.db` from the committed data alone.
- No committed file may exceed 85 MB (see [Large files](#large-files-scriptsdata_filespy)).
- Large data imports are pushed in batches of about 500 MB, so no single push approaches GitHub's 2 GB limit.
- Windows cannot create file names containing `\ : * ? " < > |`; such upstream paths are imported with `\` treated as a folder separator and the other characters replaced by `_`.
- `.gitattributes` stores everything under `data/` byte-for-byte (`-text -diff`): no line-ending conversion.

## Large files: `scripts/data_files.py`

Git hosts reject large blobs, so oversized files under `data/` are committed as chunks.

| Command | Behaviour |
|---|---|
| `check` | Lists every file under `data/` larger than **85 MB** (`LIMIT_MB`) that is not itself a part file, asks `git check-ignore` which of them Git would skip, and fails (exit 1) for any that would be committed. If Git cannot be run, it falls back to the managed `.gitignore` block. |
| `split` | Splits each file over 85 MB into **80 MB** (`CHUNK_MB`) chunks named `<name>.part001`, `<name>.part002`, … (three digits). Old `.partNNN` files for that original are deleted first, so re-splitting leaves no stale parts. The original stays on disk and is added to the managed `.gitignore` block. |
| `join` | Rebuilds every original from its parts in order. An original whose size already equals the sum of its parts is left alone. `build_database.py` runs this first. |

All commands accept `--data-dir PATH` (default `data/`).

The managed block in `.gitignore` is delimited by `# >>> split data files (managed by scripts/data_files.py; originals rebuilt by \`join\`)` and `# <<< split data files`; `split` rewrites it, so add other ignore rules outside it. The file currently split is `data/raw/EpeyKatfg/series.csv` (two parts).

## Raw CSV input (`data/raw/`)

- **Layout:** TÜİK COICOP folders (`01_Food/<store>/…`, `03_Clothing/<store>/…`, `04_Housing/<region>/<city>/…`, …) plus a few non-TÜİK top-level folders such as `EpeyKatfg/`. The folder path determines the retailer label; the rules are in [DATABASE.md](DATABASE.md#raw-csv-ingestion).
- **File name:** must contain a full date (`YYYY-MM-DD`, `DD-MM-YYYY` or `YYYYMMDD`; `-`, `_` or `.` separators). Undated files are skipped.
- **Delimiter:** comma, semicolon or tab (whichever is most frequent in the header line).
- **Encoding:** UTF-8 (with or without BOM), falling back to cp1254.
- **Columns:** schemas are scraper-specific. A file needs a price column and, ideally, a product id, name and category column. Accepted spellings are the domain's canonical columns (`inflation_dashboard/domain/prices.py`) plus the header aliases listed in [DATABASE.md](DATABASE.md#raw-csv-ingestion).

## Partitioned JSON input (`data/prices_json/`)

One file per retailer; the file stem gives the label (`Markets_Gurmar.json` → `Markets / Gurmar`, `_` → ` / `). Shape:

```json
{
  "product-id": {
    "name": "Product",
    "category": "Category",
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

The build reads only `name` (defaults to the product id), `category` (defaults to `Uncategorized`) and `prices` (`null` prices are skipped). `latest_price`, `min_price` and `max_price` are ignored and recomputed from the observations. A partition is used only when its retailer has no successfully ingested raw CSV.

## Generated inflation input (`data/inflation/`)

`/api/epeykatfg/monthly-inflation` serves `data/inflation/EpeyKatfg/monthly_inflation.csv` (override with `EPEYKATFG_MONTHLY_CSV`): a UTF-8 CSV with a header and one row per month. Values in `month`, `prev_month` and `groups` stay strings; other values are converted to numbers when they parse. Per-group columns follow the `n_<code>`, `avg_<code>` and `basic_<code>` naming. The response shape is in [FALCON_API_CONTRACT.md](FALCON_API_CONTRACT.md).

If the file is absent or has no header, the endpoint returns 200 with an empty `data` array.

Other files under `data/inflation/` are committed for reference and are not read by the API.

## Updating the data

The checklist (copy, `data_files.py check`/`split`, push batches, rebuild, verify) is in [DEVELOPMENT.md](DEVELOPMENT.md).

## Troubleshooting

- **Data endpoints return 503 `database_unavailable`:** `data/prices.db` (or `PRICES_DB_PATH`) is missing or empty. Build it with `scripts/build_database.py` (see [GETTING-STARTED.md](GETTING-STARTED.md)).
- **A retailer is missing after a build:** check the build summary's skip counts; the usual causes are an undated file name or an unrecognised price header.
