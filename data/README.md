# Runtime data mount

This directory is intentionally ignored by Git. It is the default local mount for artifacts supplied by the separate data repository.

Expected optional layout:

```text
data/
  prices.db
  prices_json/
  raw/
  inflation/
    EpeyKatfg/
      monthly_inflation.csv
```

The recommended production path is to build `prices.db` from the data repository's partitioned JSON and deploy the database as a versioned runtime artifact. Do not commit raw scraper output, cookies or the SQLite binary to this repository.

See `docs/DATA_CONTRACT.md` and `docs/DATABASE.md`.
