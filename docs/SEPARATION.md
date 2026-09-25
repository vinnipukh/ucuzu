# Separation Record

This repository was extracted from the former `inflationstudymirror` monorepo on 2026-09-24.

## Source ownership

The sibling `inflationstudymirror` data repository now owns:

- `InflationItems/`
- `Inflations/`
- scraper workflows/logs and data-only scripts
- scraper/site-analysis/inflation documentation

This repository owns:

- `frontend/`
- `inflation_dashboard/`
- Falcon server/database/benchmark scripts
- current web API/database/deployment documentation
- ignored runtime artifacts under `data/`

## Changes made during extraction

- Removed Streamlit and the legacy Python frontend client from the production web repository.
- Replaced hard-coded monorepo paths with:
  - `PRICES_DB_PATH`
  - `INFLATION_DATA_ROOT`
  - `EPEYKATFG_MONTHLY_CSV`
- Changed the SQLite default to `data/prices.db`.
- Rebuilt the JSON-to-SQLite builder around the three canonical tables and API indexes.
- Added per-retailer/date ingestion ledger rows so bounded `max_files` behavior works with sparse JSON partitions.
- Split the monolithic Python dependency manifest into backend-only dependencies.
- Added `docs/DATA_CONTRACT.md`, `docs/DATABASE.md` and current standalone setup documentation.
- Archived monorepo/Streamlit planning material under `docs/archive/`.
- Added a no-data CI path for API contract verification.

## Runtime data

The local ignored runtime mount currently contains a SQLite database built from the data repository's `InflationItems/prices_json/` and the EpeyKatfg monthly artifact. These files are not Git source and must be rebuilt/deployed from a versioned data release.

## Git

The original Git history remains in the data repository. This is a new clean Git repository. Review the extracted snapshot before creating its first commit and remote.
