# AGENTS.md

Instructions for coding agents working in the ucuzu / Inflation Study Dashboard repository (price-comparison shop at `/`, inflation dashboard at `/analiz`). Documentation index: [docs/README.md](docs/README.md).

Known code defects are listed in [docs/ARCHITECTURE.md#known-issues](docs/ARCHITECTURE.md#known-issues); do not assume documented behaviour that is listed there.

## Repository boundary

This repository owns the web application only:

| Path | Role |
|---|---|
| `frontend/` | Svelte 5 / SvelteKit production SPA: the ucuzu shop (`src/routes/(shop)/`) and the dashboard (`src/routes/analiz/`) |
| `inflation_dashboard/` | Falcon API, domain/application logic, SQLite adapter |
| `scripts/` | API server, database build/migration, verification and benchmarks |
| `data/` | Committed scraper output (`raw/`, `prices_json/`, `inflation/`); no scraper source code belongs here |
| `docs/` | Web architecture, API contract, database and deployment documentation |

Source layout and request flow: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Scrapers, inflation calculators and TÜİK methodology live in the separate data repository [`vinnipukh/inflationstudymirror`](https://github.com/vinnipukh/inflationstudymirror) (mirror of the upstream [`urazkagangunes/InflationResearchStudy`](https://github.com/urazkagangunes/InflationResearchStudy)). Their output is committed here under `data/`. Do not add their source code to this repository.

## Data rules

The API must not assume that a sibling monorepo exists; everything it needs is in `data/` or built from it.

- **Commit the data, never the database.** Per-retailer JSON price histories (`data/prices_json/`, the source of every retailer's prices), the mirror's EpeyKatfg reference files (`data/raw/EpeyKatfg/`, no CSVs) and inflation artifacts (`data/inflation/`) are committed. New scrapes are converted to JSON with `scripts/csv_to_json.py`; do not add new price CSVs to `data/raw/`. `*.db`, `*.db-wal`, `*.db-shm` are ignored everywhere and must never be committed.
- **Always commit a working database build script.** `scripts/build_database.py` must rebuild `data/prices.db` from the committed `data/` tree with no other inputs. Any change to data layout, file formats, retailer folders or the schema must update this script (and `tests/test_build_database.py`) in the same commit.
- **No committed file may exceed 85 MB.** Before committing data, run `uv run python scripts/data_files.py check`. Oversized files are either split with `scripts/data_files.py split` (committed as `.partNNN` chunks, original listed in the managed `.gitignore` block and rebuilt by `join`) or added to `.gitignore`.
- Push large data commits in batches of about 500 MB so no single push approaches GitHub's 2 GB limit.
- Never commit `.env`, cookies, credentials or browser profiles.
- `PRICES_DB_PATH` selects the runtime SQLite database; default: `data/prices.db`.
- `EPEYKATFG_MONTHLY_CSV` selects the monthly inflation artifact; default: `data/inflation/EpeyKatfg/monthly_inflation.csv`.

The API serves only from the SQLite database; a missing database gives HTTP 503 `database_unavailable`. Details: [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) (data layout, `data_files.py`) and [docs/DATABASE.md](docs/DATABASE.md) (schema, build). Environment variables: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Architecture boundaries

- `domain/`, `application/` and `adapters/` remain independent of Falcon and frontend frameworks.
- `api/` owns HTTP concerns and must not import browser UI code.
- `frontend/` communicates only through the documented HTTP API.
- Database access belongs in adapters; API resources must not import `sqlite3`.
- Do not add legacy Streamlit dependencies or entrypoints.
- Keep TypeScript types and `docs/FALCON_API_CONTRACT.md` synchronized with endpoint changes.

Full boundary rules and conventions: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development

Same commands as the summary in [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md), which explains each step. Importing new data from the upstream data repository is walked through in [docs/SETUP.md](docs/SETUP.md#4-take-new-data-from-inflationresearchstudy):

```bash
uv sync --extra dev
uv run python scripts/data_files.py join
uv run python scripts/build_database.py
uv run pytest
uv run python scripts/verify_falcon_api.py
uv run python scripts/run_falcon_server.py --engine granian --port 8000
cd frontend && npm install && npm run dev
```

Run the API and the frontend dev server as separate processes. Before committing: `uv run pytest` and `cd frontend && npm run check && npm run build`.

## Change policy

- Preserve the `{data, meta, errors}` response envelope.
- Preserve read-only SQLite production behavior unless a migration is explicitly designed.
- Changes to data or the database build follow the **Data rules** above.
- Update API, database, configuration and user documentation together with behavior changes; the per-change checklists are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
- Historical Streamlit/SQLite planning material belongs under `docs/archive/`; do not present it as current setup guidance.
