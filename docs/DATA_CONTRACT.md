# Data Contract

This document defines the boundary between the `inflationstudymirror` data repository and this web repository.

## Ownership

| Artifact | Producer | Consumer |
|---|---|---|
| Raw retailer CSVs | Scraper workflows in `InflationItems/Datas/` | `scripts/build_database.py`; optional CSV fallback |
| Partitioned JSON histories | Scraper/ETL code in `InflationItems/prices_json/` | `scripts/build_database.py` (retailers without raw CSVs) |
| Generated inflation CSVs | Calculators in `Inflations/Datas/` | API artifact endpoints |
| SQLite serving database | Web repository build/deployment job | Falcon WSGI API |

The SQLite file is a serving artifact, not the data repository's source of truth.

## Committed data

Scraper output is copied into this repository and committed:

| Source path (data repository) | Path here |
|---|---|
| `InflationItems/Datas/` | `data/raw/` |
| `InflationItems/prices_json/` | `data/prices_json/` |
| `Inflations/Datas/` | `data/inflation/` |

Sources are `vinnipukh/inflationstudymirror` and its upstream `urazkagangunes/InflationResearchStudy`. When both have a file at the same path, the mirror's copy wins (upstream renamed CSV headers such as `product-name,product_price` → `product_name,price`; both spellings are accepted).

Rules:

- `*.db` files are never committed. `scripts/build_database.py` must always rebuild `data/prices.db` from the committed data alone.
- No committed file may exceed 85 MB. `scripts/data_files.py check` enforces this; `scripts/data_files.py split` commits oversized files as `.partNNN` chunks, and `build_database.py` rejoins them.
- Large data imports are pushed in batches of about 500 MB.
- Windows cannot create file names containing `\ : * ? " < > |`; such upstream paths are imported with `\` treated as a folder separator and other characters replaced by `_`.

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `INFLATION_DATA_ROOT` | Root of externally supplied raw CSV snapshots | `data/raw` |
| `PRICES_DB_PATH` | Runtime SQLite database | `data/prices.db` |
| `EPEYKATFG_MONTHLY_CSV` | EpeyKatfg monthly inflation CSV | `data/inflation/EpeyKatfg/monthly_inflation.csv` |

Paths may point to a sibling checkout, mounted volume, extracted release archive or CI artifact. The API does not require a repository named `inflationstudymirror` to exist next to it.

## Partitioned JSON input

Each JSON file represents one logical retailer partition:

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

The builder derives the retailer label from the file stem and creates normalized observation rows plus the ingestion ledger.

## Raw CSV input

CSV schemas remain source-specific. The shared reader supports common price/product/category column variants, UTF-8 with BOM, comma/semicolon delimiters and filename-driven dates. The fallback must remain bounded by retailer, date and file count.

## Generated inflation input

The EpeyKatfg endpoint consumes a CSV with a header and one row per month. The current web contract expects the columns documented in `docs/FALCON_API_CONTRACT.md`; per-group columns use the `n_<code>`, `avg_<code>` and `basic_<code>` naming convention.

If the artifact is absent, the endpoint returns a valid empty response rather than importing code from the data repository.

## Recommended publication flow

1. Run and validate the data repository's scrapers and inflation calculators.
2. Copy new or changed files into `data/raw`, `data/prices_json` and `data/inflation`, recording the source commits in the commit message.
3. Run `uv run python scripts/data_files.py check` (split or ignore anything over 85 MB) and commit in batches of about 500 MB.
4. Build `data/prices.db` with `uv run python scripts/build_database.py`.
5. Run API verification against the built database.
6. Deploy the database as a read-only runtime artifact.
7. Rebuild when new data is committed; do not mutate the database in API workers.
