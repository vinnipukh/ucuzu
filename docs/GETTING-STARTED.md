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

Copy `.env.example` to `.env` or export variables in your shell. The defaults already point at the committed `data/` tree, so no configuration is needed for a normal checkout.

## Build the serving database

```bash
uv run python scripts/build_database.py
```

This rebuilds `data/prices.db` from the committed scraper data (`data/raw`, `data/prices_json`). The database is never committed. See `docs/DATABASE.md`.

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

- **Data endpoints return 503 `database_unavailable`:** the database is missing or empty; run `uv run python scripts/build_database.py` (or point `PRICES_DB_PATH` at a built database).
- **Epey monthly view is empty:** set `EPEYKATFG_MONTHLY_CSV` to the generated artifact.
- **Frontend cannot reach API:** verify port 8000 and `VITE_API_BASE_URL`/CORS settings.
- **Read-only SQLite error:** keep the database directory and WAL sidecars available to the reader; do not deploy a WAL database on a filesystem that prevents SQLite from opening its sidecar state.
- **Large first request:** use bounded defaults, warm the API after deployment or build precomputed artifacts before traffic.
