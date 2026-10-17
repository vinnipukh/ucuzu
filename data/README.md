# Data

This directory is committed. It holds scraper output copied from the `inflationstudymirror` data repository (and its upstream, `urazkagangunes/InflationResearchStudy`). The SQLite database built from it is **not** committed.

```text
data/
  raw/            scraped price CSVs, grouped by TÜİK COICOP folder (01_Food/Gurmar/...)
  prices_json/    partitioned JSON price histories (used only for retailers without raw CSVs)
  inflation/      generated inflation artifacts (EpeyKatfg/monthly_inflation.csv, ...)
  prices.db       built locally, ignored by Git
```

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
