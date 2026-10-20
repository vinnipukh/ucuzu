# Data

This directory is committed. It holds scraper output from the `inflationstudymirror` data repository (and its upstream, `urazkagangunes/InflationResearchStudy`). The SQLite database built from it is **not** committed.

```text
data/
  prices_json/    one JSON price history per retailer (<Group>_<Store>.json): the source of every retailer's prices
  raw/            scraper reference files (URL lists, notes, caches) in TÜİK COICOP folders; no price CSVs
  inflation/      generated inflation artifacts (EpeyKatfg/monthly_inflation.csv, ...)
  prices.db       built locally, ignored by Git
```

New upstream scrapes are merged into `prices_json/` with `scripts/csv_to_json.py`; price CSVs are not committed (see `docs/SETUP.md`, section 4).

Build the database:

```bash
uv run python scripts/build_database.py
```

Before committing new data, make sure no file exceeds 85 MB:

```bash
uv run python scripts/data_files.py check   # fails on oversized files
uv run python scripts/data_files.py split   # commits them as .partNNN chunks instead
```

Split originals are listed in the managed block at the end of `.gitignore` and are rebuilt automatically by `build_database.py` (or `scripts/data_files.py join`).

See `docs/DATA_CONTRACT.md` and `docs/DATABASE.md`.
