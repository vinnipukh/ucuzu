# Data Contract

This document defines the boundary between the `inflationstudymirror` data repository and this web repository.

## Ownership

| Artifact | Producer | Consumer |
|---|---|---|
| Raw retailer CSVs | Scraper workflows in `InflationItems/Datas/` | Optional CSV fallback or SQLite migration |
| Partitioned JSON histories | Scraper/ETL code in `InflationItems/prices_json/` | `scripts/build_sqlite_from_json.py` |
| Generated inflation CSVs | Calculators in `Inflations/Datas/` | API artifact endpoints |
| SQLite serving database | Web repository build/deployment job | Falcon WSGI/ASGI API |

The SQLite file is a serving artifact, not the data repository's source of truth.

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
2. Generate a dated release or CI artifact containing `prices_json/` and required inflation CSVs.
3. Verify checksums and record the source commit.
4. Build `data/prices.db` in the web repository.
5. Run API verification against the built database.
6. Deploy the database as a read-only runtime artifact.
7. Rebuild when a new data release is published; do not mutate the database in API workers.
