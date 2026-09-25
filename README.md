# Inflation Study Dashboard

Standalone Svelte 5 / SvelteKit frontend, Falcon API backend, and SQLite serving layer for the Inflation Study project.

Scrapers, raw price datasets and inflation calculations are maintained separately in [`inflationstudymirror`](https://github.com/vinnipukh/inflationstudymirror). This repository consumes published data artifacts; it does not contain scraper or calculator code.

## Architecture

```text
inflationstudymirror (data repository)
  InflationItems/Datas/       raw CSV snapshots
  InflationItems/prices_json/ partitioned price histories
  Inflations/Datas/           generated inflation artifacts
                 │
                 │ external paths / deployment volume
                 ▼
inflationstudymirror-web
  scripts/build_sqlite_from_json.py
                 │
                 ▼
  data/prices.db → Falcon API → Svelte SPA
```

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- npm

## Setup

```bash
git clone <web-repository-url>
cd inflationstudymirror-web
uv sync
cd frontend && npm install && cd ..
```

Copy `.env.example` to `.env` when overriding defaults. Never commit `.env`.

## Supply data

The data repository can be checked out as a sibling and exposed through environment variables. PowerShell example:

```powershell
$env:INFLATION_DATA_ROOT = "..\inflationstudymirror\InflationItems\Datas"
$env:EPEYKATFG_MONTHLY_CSV = "..\inflationstudymirror\Inflations\Datas\EpeyKatfg\monthly_inflation.csv"

uv run python scripts/build_sqlite_from_json.py `
  --json-dir ..\inflationstudymirror\InflationItems\prices_json `
  --db-path data\prices.db
```

Alternatively, build from the raw CSV archive:

```powershell
uv run python scripts/migrate_csv_to_sqlite.py `
  --datas-dir ..\inflationstudymirror\InflationItems\Datas `
  --db-path data\prices.db
```

The SQLite file is a generated runtime artifact and is not committed. See `docs/DATA_CONTRACT.md` and `docs/DATABASE.md`.

## Run

Terminal 1 — API:

```bash
uv run python scripts/run_falcon_server.py --engine granian --workers 4 --threads 8 --port 8000
```

Terminal 2 — Svelte frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000` during development.

## API

Nine routes are registered in both WSGI and ASGI applications:

| Route | Purpose |
|---|---|
| `GET /api/health` | Lightweight health/readiness response |
| `GET /api/inventory` | Retailers, date bounds and inventory counts |
| `GET /api/products/search` | Product autocomplete |
| `GET /api/product` | Product detail and complete price history |
| `GET /api/history` | Filtered price observations |
| `GET /api/retailer-averages` | Average/median retailer trends |
| `GET /api/movers` | Largest gains and drops |
| `GET /api/coverage` | Dataset coverage and diagnostics |
| `GET /api/epeykatfg/monthly-inflation` | Generated EpeyKatfg monthly inflation series |

All routes use the stable `{data, meta, errors}` envelope. The canonical contract is `docs/FALCON_API_CONTRACT.md`.

## Frontend

The production SPA has five views:

1. Product Explorer
2. Retailer Averages
3. Price Movers
4. Coverage Overview
5. EpeyKatfg Monthly

See `frontend/README.md` for frontend configuration and design details.

## Structure

```text
frontend/                 SvelteKit SPA
inflation_dashboard/
  domain/                 normalization and shared data contracts
  application/            dashboard use cases
  adapters/               SQLite, CSV and async repositories
  api/                    Falcon WSGI/ASGI resources and middleware
scripts/                  server, database, verification and benchmarks
data/                     ignored runtime mount
docs/                     current web documentation
docs/archive/             historical monorepo and Streamlit material
```

## Verification

```bash
# Backend/API
uv run python scripts/verify_falcon_api.py
uv run python scripts/verify_asgi_api.py
uv run python scripts/verify_redis_store.py

# Frontend
cd frontend
npm run check
npm run build
```

Database and load test scripts require a built `data/prices.db` or an explicitly configured database path.

## Documentation

- `docs/README.md` — documentation index
- `docs/ARCHITECTURE.md` — web application architecture
- `docs/DATA_CONTRACT.md` — data-repository-to-web interface
- `docs/DATABASE.md` — SQLite schema, build and operation
- `docs/FALCON_API_CONTRACT.md` — canonical HTTP contract
- `docs/GETTING-STARTED.md` — local setup
- `docs/DEVELOPMENT.md` — development workflow
- `docs/CONFIGURATION.md` — environment and runtime settings
- `docs/TESTING.md` — verification commands
- `docs/USER_GUIDE.md` — dashboard usage
