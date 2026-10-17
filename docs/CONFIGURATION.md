# Configuration

## Data locations

| Variable | Default | Purpose |
|---|---|---|
| `PRICES_DB_PATH` | `data/prices.db` | Runtime SQLite database |
| `INFLATION_DATA_ROOT` | `data/raw` | Optional bounded raw CSV fallback |
| `EPEYKATFG_MONTHLY_CSV` | `data/inflation/EpeyKatfg/monthly_inflation.csv` | Generated monthly inflation artifact |

## Falcon

| Variable | Default | Purpose |
|---|---|---|
| `FALCON_CORS_ORIGINS` | `*` in app code | Comma-separated browser origins |
| `FALCON_TIMING_LOG` | unset | Enable request timing logs in WSGI app |

Restrict CORS in deployed environments, for example:

```dotenv
FALCON_CORS_ORIGINS=https://dashboard.example.org
```

## SQLite

| Variable | Default |
|---|---:|
| `SQLITE_BUSY_TIMEOUT` | `5000` ms |
| `SQLITE_CACHE_SIZE` | `-128000` KiB |
| `SQLITE_MMAP_SIZE` | `1073741824` bytes |

The launcher accepts `--sqlite-db` and exports the selected path as `PRICES_DB_PATH` to workers.

## Frontend

`frontend/.env.example`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Set it to an empty value for same-origin `/api` requests. A production static host can serve the Svelte build and proxy `/api` to Falcon.

## Secrets

Never commit `.env`, API keys, cookies, browser profiles or database files. `.gitignore` excludes common secret and runtime-artifact patterns.
