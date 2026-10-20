# Configuration

This file owns every environment variable and launcher flag. Commands for installing and running are in [GETTING-STARTED.md](GETTING-STARTED.md).

## How values are read

- **No `.env` file is loaded.** Nothing in the API or scripts uses dotenv. [`.env.example`](../.env.example) only lists the variables; export them in the shell or the service manager (systemd unit, container environment) before starting the API. This is listed under [Known issues](ARCHITECTURE.md#known-issues).
- `.env.example` sets `FALCON_CORS_ORIGINS=http://localhost:5173`, which differs from the code default `*`. Copying the example does nothing unless the value is exported.
- The frontend is different: Vite reads `frontend/.env` (and `frontend/.env.*`) at dev/build time for `VITE_*` variables. See [`frontend/.env.example`](../frontend/.env.example).
- Relative paths in `PRICES_DB_PATH` and `EPEYKATFG_MONTHLY_CSV` resolve against the **current working directory** of the process, not the repository root.

## API and data variables

| Variable | Default | Read by | Effect |
|---|---|---|---|
| `PRICES_DB_PATH` | `data/prices.db` (repository root) | `inflation_dashboard/adapters/sqlite_price_repository.py:36`; `scripts/run_falcon_server.py:364`; `scripts/build_database.py:616` | SQLite database the API serves from, and the default output of the database build. If the file is missing or 0 bytes, data endpoints return 503 `database_unavailable`. |
| `EPEYKATFG_MONTHLY_CSV` | `data/inflation/EpeyKatfg/monthly_inflation.csv` | `inflation_dashboard/application/epeykatfg_monthly.py:20` | CSV served by `/api/epeykatfg/monthly-inflation`. `~` is expanded. |
| `FALCON_CORS_ORIGINS` | `*` | `inflation_dashboard/api/falcon_app.py:83`; `scripts/run_falcon_server.py:359` | Allowed browser origins, comma-separated. `*` (alone) allows any origin. Only needed when the SPA calls the API from another origin. |
| `FALCON_TIMING_LOG` | unset (off) | `inflation_dashboard/api/falcon_app.py:42` | `1`, `true`, `yes` or `on` (case-insensitive) logs one INFO line per request (method, path, status, duration, cache hit) on the logger `inflation_dashboard.api.timing`. The line appears only if the hosting process shows INFO logs. |
| `SQLITE_BUSY_TIMEOUT` | `5000` (ms) | `inflation_dashboard/adapters/sqlite_price_repository.py:56` | `PRAGMA busy_timeout` on every connection. |
| `SQLITE_CACHE_SIZE` | `-128000` (negative = KiB, so 128 MiB) | `inflation_dashboard/adapters/sqlite_price_repository.py:57` | `PRAGMA cache_size` per connection (one reusable read-only connection per worker thread). |
| `SQLITE_MMAP_SIZE` | `1073741824` (1 GiB) | `inflation_dashboard/adapters/sqlite_price_repository.py:58` | `PRAGMA mmap_size` per connection. |

> **Changed 2026-10-17:** `INFLATION_DATA_ROOT` was removed with the runtime CSV fallback; previously it selected the raw CSV fallback root (default `data/raw`). See [change history](README.md#change-history).

## Launcher variables

`scripts/run_falcon_server.py` reads these only as defaults for its flags; a flag on the command line wins.

| Variable | Default | Read by | Effect |
|---|---|---|---|
| `HOST` | `127.0.0.1` | `scripts/run_falcon_server.py:330` | Bind address (`--host`). |
| `PORT` | `8000` | `scripts/run_falcon_server.py:336` | Listen port (`--port`). |
| `WEB_CONCURRENCY` | CPU count, clamped to 1–8 (`scripts/run_falcon_server.py:317`) | `scripts/run_falcon_server.py:342` | Worker processes (`--workers`). |
| `SERVER_THREADS` | `8` | `scripts/run_falcon_server.py:348` | Threads per worker (`--threads`). |
| `SERVER_BACKLOG` | `2048` | `scripts/run_falcon_server.py:354` | Socket backlog (`--backlog`). |

## Launcher flags

From `uv run python scripts/run_falcon_server.py --help`:

| Flag | Default | Effect |
|---|---|---|
| `--engine {granian,gunicorn,waitress}` | `granian` | WSGI server. If Granian is not installed the launcher falls back to Gunicorn, and vice versa. Waitress gets `workers × threads` threads in one process. |
| `--host HOST` | `HOST` or `127.0.0.1` | Bind address. |
| `--port PORT` | `PORT` or `8000` | Listen port. |
| `--workers N` | `WEB_CONCURRENCY` or CPU count (1–8) | Worker processes. |
| `--threads N` | `SERVER_THREADS` or `8` | Threads per worker. |
| `--backlog N` | `SERVER_BACKLOG` or `2048` | Socket backlog. |
| `--cors-origins LIST` | `FALCON_CORS_ORIGINS` or `*` | Exported as `FALCON_CORS_ORIGINS` for the workers. |
| `--sqlite-db PATH` | `PRICES_DB_PATH` or `data/prices.db` | Database to serve. **Precedence: `--sqlite-db` > `PRICES_DB_PATH` > `data/prices.db`.** The resolved absolute path is exported as `PRICES_DB_PATH` for the workers. |
| `--log-level LEVEL` | `info` | One of `critical`, `error`, `warning`, `warn`, `info`, `debug`; passed to Granian/Gunicorn. |
| `--dry-run` | off | Print the banner and the server command without starting it. |

> **Changed 2026-10-17:** `--sqlite-db` defaults to `PRICES_DB_PATH`, and `--no-sqlite-readonly` and the exports `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS` and `SQLITE_URI` were removed; previously the launcher always overwrote `PRICES_DB_PATH` with its own default and exported those never-read variables. See [change history](README.md#change-history).

At startup the launcher opens the database read-write once to switch it to WAL mode if needed, then exports `PRICES_DB_PATH`, `SQLITE_BUSY_TIMEOUT`, `SQLITE_CACHE_SIZE` and `SQLITE_MMAP_SIZE` (current values or defaults) and prepends the repository root to `PYTHONPATH`. Request connections are always read-only (`mode=ro`). See [DATABASE.md](DATABASE.md).

When the WSGI app is served without the launcher (for example `granian --interface wsgi --factory inflation_dashboard.api.falcon_app:create_app`), set the variables above directly.

## Frontend

| Variable | Default | Read by | Effect |
|---|---|---|---|
| `VITE_API_BASE_URL` | empty | `frontend/src/lib/stores/filters.svelte.ts:3` (build time) | API origin baked into the build. **Empty or unset means same-origin `/api/...`**: the Vite dev proxy forwards `/api` to `http://localhost:8000` in `npm run dev`, and in production a reverse proxy must route `/api` to Falcon. A full URL (trailing slashes removed) points the SPA at another origin; then allow the SPA origin in `FALCON_CORS_ORIGINS`. Users can override the URL at runtime in the sidebar's API settings. |

> **Changed 2026-10-17:** an empty or unset `VITE_API_BASE_URL` means same-origin `/api`; previously it meant `http://localhost:8000`. See [change history](README.md#change-history).

## Secrets

Never commit `.env`, API keys, cookies, browser profiles or database files. `.gitignore` excludes common secret and runtime-artifact patterns.
