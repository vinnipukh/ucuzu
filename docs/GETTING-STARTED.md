# Getting Started

## Prerequisites

- Python 3.14+
- uv
- Node.js 20+
- npm
- A data artifact from the separate `inflationstudymirror` repository

## Install

```bash
uv sync
cd frontend
npm install
cd ..
```

## Configure

Copy `.env.example` to `.env` or export variables in your shell. For a sibling data checkout on Windows PowerShell:

```powershell
$env:INFLATION_DATA_ROOT = "..\inflationstudymirror\InflationItems\Datas"
$env:EPEYKATFG_MONTHLY_CSV = "..\inflationstudymirror\Inflations\Datas\EpeyKatfg\monthly_inflation.csv"
```

## Build the serving database

From partitioned JSON:

```powershell
uv run python scripts/build_sqlite_from_json.py `
  --json-dir ..\inflationstudymirror\InflationItems\prices_json `
  --db-path data\prices.db
```

Or from raw CSV:

```powershell
uv run python scripts/migrate_csv_to_sqlite.py `
  --datas-dir ..\inflationstudymirror\InflationItems\Datas `
  --db-path data\prices.db
```

## Run the API

```bash
uv run python scripts/run_falcon_server.py --engine granian --workers 4 --threads 8 --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Run the frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The Vite development server proxies `/api` to port 8000.

## Verify

```bash
uv run python scripts/verify_falcon_api.py
cd frontend && npm run check && npm run build
```

## Troubleshooting

- **API has no inventory:** confirm `PRICES_DB_PATH` points to a built database, or configure `INFLATION_DATA_ROOT` for fallback reads.
- **Epey monthly view is empty:** set `EPEYKATFG_MONTHLY_CSV` to the generated artifact.
- **Frontend cannot reach API:** verify port 8000 and `VITE_API_BASE_URL`/CORS settings.
- **Read-only SQLite error:** keep the database directory and WAL sidecars available to the reader; do not deploy a WAL database on a filesystem that prevents SQLite from opening its sidecar state.
- **Large first request:** use bounded defaults, warm the API after deployment or build precomputed artifacts before traffic.
