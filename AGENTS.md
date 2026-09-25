# AGENTS.md

Instructions for coding agents working in the Inflation Study Dashboard repository.

## Repository boundary

This repository owns the web application only:

| Path | Role |
|---|---|
| `frontend/` | Svelte 5 / SvelteKit production SPA |
| `inflation_dashboard/` | Falcon API, domain/application logic, SQLite and CSV adapters |
| `scripts/` | API server, database build/migration, verification and benchmarks |
| `data/` | Ignored runtime data mount; no scraper source code belongs here |
| `docs/` | Web architecture, API contract, database and deployment documentation |

Scrapers, raw datasets, inflation calculators and TÜİK methodology live in the separate `inflationstudymirror` data repository. Do not add them back to this repository.

## External data contract

The API must not assume that a sibling monorepo exists.

- `PRICES_DB_PATH` selects the runtime SQLite database; default: `data/prices.db`.
- `INFLATION_DATA_ROOT` selects the optional raw CSV fallback root; default: `data/raw`.
- `EPEYKATFG_MONTHLY_CSV` selects the monthly inflation artifact; default: `data/inflation/EpeyKatfg/monthly_inflation.csv`.
- Never commit `.env`, cookies, credentials, raw scraper output or a SQLite database.

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
uv sync
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
- Update API, database, configuration and user documentation together with behavior changes.
- Historical Streamlit/SQLite planning material belongs under `docs/archive/`; do not present it as current setup guidance.
