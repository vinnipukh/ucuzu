# AGENTS.md

Instructions for coding agents working in the Inflation Study Dashboard repository.

## Repository boundary

This repository owns the web application only:

| Path | Role |
|---|---|
| `frontend/` | Svelte 5 / SvelteKit production SPA |
| `inflation_dashboard/` | Falcon API, domain/application logic, SQLite and CSV adapters |
| `scripts/` | API server, database build/migration, verification and benchmarks |
| `data/` | Committed scraper output (`raw/`, `prices_json/`, `inflation/`); no scraper source code belongs here |
| `docs/` | Web architecture, API contract, database and deployment documentation |

Scrapers, inflation calculators and TÜİK methodology live in the separate data repository [`vinnipukh/inflationstudymirror`](https://github.com/vinnipukh/inflationstudymirror) (mirror of the upstream [`urazkagangunes/InflationResearchStudy`](https://github.com/urazkagangunes/InflationResearchStudy)). Their output is committed here under `data/`. Do not add their source code to this repository.

## Data rules

The API must not assume that a sibling monorepo exists; everything it needs is in `data/` or built from it.

- **Commit the data, never the database.** Scraped CSVs (`data/raw/`), JSON partitions (`data/prices_json/`) and inflation artifacts (`data/inflation/`) are committed. `*.db`, `*.db-wal`, `*.db-shm` are ignored everywhere and must never be committed.
- **Always commit a working database build script.** `scripts/build_database.py` must rebuild `data/prices.db` from the committed `data/` tree with no other inputs. Any change to data layout, file formats, retailer folders or the schema must update this script (and `tests/test_build_database.py`) in the same commit.
- **No committed file may exceed 85 MB.** Before committing data, run `uv run python scripts/data_files.py check`. Oversized files are either split with `scripts/data_files.py split` (committed as `.partNNN` chunks, original listed in the managed `.gitignore` block and rebuilt by `join`) or added to `.gitignore`.
- Push large data commits in batches of about 500 MB so no single push approaches GitHub's 2 GB limit.
- Never commit `.env`, cookies, credentials or browser profiles.
- `PRICES_DB_PATH` selects the runtime SQLite database; default: `data/prices.db`.
- `EPEYKATFG_MONTHLY_CSV` selects the monthly inflation artifact; default: `data/inflation/EpeyKatfg/monthly_inflation.csv`.

See `docs/DATA_CONTRACT.md` and `docs/DATABASE.md`.

## Architecture boundaries

- `domain/`, `application/` and `adapters/` remain independent of Falcon and frontend frameworks.
- `api/` owns HTTP concerns and must not import browser UI code.
- `frontend/` communicates only through the documented HTTP API.
- Database access belongs in adapters; API resources must not import `sqlite3`.
- Do not add legacy Streamlit dependencies or entrypoints.
- Keep TypeScript types and `docs/FALCON_API_CONTRACT.md` synchronized with endpoint changes.

## Development

```bash
uv sync --extra dev
uv run python scripts/build_database.py
uv run pytest
uv run python scripts/verify_falcon_api.py
cd frontend && npm install && npm run check && npm run build
```

Run the API and frontend as separate processes:

```bash
uv run python scripts/run_falcon_server.py --engine granian --port 8000
cd frontend && npm run dev
```

## Change policy

- Preserve the `{data, meta, errors}` response envelope.
- Preserve read-only SQLite production behavior unless a migration is explicitly designed.
- Changes to data or the database build follow the **Data rules** above.
- Update API, database, configuration and user documentation together with behavior changes.
- Historical Streamlit/SQLite planning material belongs under `docs/archive/`; do not present it as current setup guidance.
