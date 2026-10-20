# Getting Started

This page owns the install, build, run and verify commands. It takes you from `git clone` to a running API, shop and dashboard. [SETUP.md](SETUP.md) is a longer walkthrough of the same steps that also covers importing new scrapes from the upstream data repository.

## Prerequisites

- **Python ≥ 3.14** (`requires-python` in `pyproject.toml`).
- **[uv](https://docs.astral.sh/uv/)** for Python dependencies and commands.
- **Node.js 24 LTS** recommended (`frontend/.nvmrc`); **≥ 22.12** is the minimum (`engines` in `frontend/package.json`; Vite 8 needs `^20.19 || >=22.12`, and Node 20 is end-of-life).
- **npm** (ships with Node.js).
- About 8 GB of free disk: the data committed under `data/` (`prices_json/`, `inflation/`, `raw/`) takes about 3 GB checked out, plus about 1 GB of Git history; the built database takes about 1.6 GB, and the build needs scratch space next to it.

No other repository or data download is needed: everything the API serves is built from the committed `data/` tree.

## Command summary

```bash
uv sync --extra dev
uv run python scripts/data_files.py join
uv run python scripts/build_database.py
uv run pytest
uv run python scripts/verify_falcon_api.py
uv run python scripts/run_falcon_server.py --engine granian --port 8000
cd frontend && npm install && npm run dev
```

The steps below explain each line. Run them from the repository root.

## 1. Clone and install

```bash
git clone https://github.com/vinnipukh/ucuzu.git
cd ucuzu
uv sync --extra dev
```

`--extra dev` installs pytest; plain `uv sync` does not.

## 2. Rejoin split data files

```bash
uv run python scripts/data_files.py join
```

Files over 85 MB are committed as `.partNNN` chunks. `join` rebuilds the originals (no file is split today) and skips any that are already intact. The database build also runs it, so this step is only needed if you want the files before building. Details: [DATA_CONTRACT.md](DATA_CONTRACT.md#large-files-scriptsdata_filespy).

## 3. Build the database

```bash
uv run python scripts/build_database.py
```

Builds `data/prices.db` (about 1.6 GB) from the per-retailer JSON files in `data/prices_json` (and any dated CSVs under `data/raw`, none today), including the price-comparison columns the shop needs. It takes several minutes (about 5 on an 8-core machine) and uses all CPU cores but one (`--workers` to change). The database is never committed; rebuild it after pulling new data. Options and pipeline: [DATABASE.md](DATABASE.md). On Windows, stop the API first: an open database cannot be replaced.

## 4. Run the tests

```bash
uv run pytest
uv run python scripts/verify_falcon_api.py
```

`pytest` needs no database. `verify_falcon_api.py` checks import boundaries and response envelopes in-process; with a built database it exercises every data endpoint, without one it checks the 503 responses. More in [TESTING.md](TESTING.md).

## 5. Run the API

```bash
uv run python scripts/run_falcon_server.py --engine granian --port 8000
```

Check it from another terminal: `curl http://localhost:8000/api/health` should return `{"data": {"status": "ok", "database": "available"}, …}`. Flags (`--workers`, `--threads`, `--sqlite-db`, …) and environment variables are in [CONFIGURATION.md](CONFIGURATION.md). `uv run python scripts/run_falcon_server.py --help` lists them.

The server runs in the foreground; Ctrl+C stops it. On Linux and macOS the launcher replaces itself with the server process. On Windows it stays running as the parent and puts the server and its worker processes in a job that Windows kills when the launcher exits, so stopping the launcher, even by killing it, never leaves workers listening on the port.

## 6. Run the frontend

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` for the ucuzu shop and `http://localhost:5173/analiz` for the dashboard. Usage is described in [USER_GUIDE.md](USER_GUIDE.md).

## How the dashboard reaches the API

`VITE_API_BASE_URL` is empty by default, so the SPA requests **same-origin `/api/...`**.

- **Development:** `npm run dev` proxies `/api` to `http://localhost:8000` (`frontend/vite.config.ts`). Nothing to configure.
- **`npm run preview` and static hosting have no proxy.** Without one of the setups below, the dashboard shows an API error.
- **Production, one origin (recommended):** build with `cd frontend && npm run build`, serve `frontend/build/` and route `/api` to Falcon with a reverse proxy (example below). No CORS setup is needed.
- **Production, separate origins:** set `VITE_API_BASE_URL=https://api.example.org` when running `npm run build`, and allow the dashboard's origin on the API with `FALCON_CORS_ORIGINS=https://dashboard.example.org`.

Users can also change the API URL at runtime in the sidebar's API settings.

### Reverse-proxy example (nginx)

```nginx
server {
    listen 80;
    server_name dashboard.example.org;
    root /srv/ucuzu/frontend/build;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

The API compresses its own responses (gzip with ETags), so the proxy does not need to.

## Before committing

```bash
uv run pytest
cd frontend && npm run check && npm run build
```

Data changes also need `uv run python scripts/data_files.py check`. The per-change checklists are in [DEVELOPMENT.md](DEVELOPMENT.md).

## Troubleshooting

- **Data endpoints return 503 `database_unavailable`** (`/api/health` shows `"database": "unavailable"`): the database file is missing or empty. Run `uv run python scripts/build_database.py`, or point `PRICES_DB_PATH` / `--sqlite-db` at a built database, then restart the API.
- **Shop pages show 503 `database_outdated`** (the dashboard still works): the database was built before the shop's catalog columns existed. Rebuild it with `uv run python scripts/build_database.py`, then restart the API.
- **Shop or dashboard shows a network error:** the API is not running on port 8000, or (outside `npm run dev`) nothing routes `/api` to it. See [How the dashboard reaches the API](#how-the-dashboard-reaches-the-api).
- **Values in `.env` are ignored:** nothing loads `.env`; export the variables instead ([CONFIGURATION.md](CONFIGURATION.md)).
- **EpeyKatfg monthly view is empty:** `data/inflation/EpeyKatfg/monthly_inflation.csv` (or `EPEYKATFG_MONTHLY_CSV`) is missing.
- **Build fails to replace the database on Windows:** stop the API (and anything else holding `data/prices.db` open) and rebuild.
- **Read-only SQLite errors:** WAL readers need the `-wal`/`-shm` files next to the database; keep that directory accessible to the API process.
