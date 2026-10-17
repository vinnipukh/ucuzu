# Development

## Source layout

| Path | Role |
|---|---|
| `frontend/src/lib/api/` | Browser HTTP client |
| `frontend/src/lib/types/` | TypeScript API contracts |
| `frontend/src/lib/views/` | Dashboard views |
| `inflation_dashboard/domain/` | Normalization and shared contracts |
| `inflation_dashboard/application/` | Use cases and output schemas |
| `inflation_dashboard/adapters/` | SQLite, CSV and async repositories |
| `inflation_dashboard/api/` | Falcon HTTP resources and middleware |
| `scripts/` | Runtime, database, verification and benchmark tools |

## Local commands

```bash
# API
uv run python scripts/run_falcon_server.py --engine granian --port 8000

# API checks
uv run python scripts/verify_falcon_api.py

# Database
uv run python scripts/build_database.py
uv run python scripts/data_files.py check
uv run python scripts/test_sqlite_adapter.py

# Frontend
cd frontend
npm run dev
npm run check
npm run build
npm run preview
```

## API changes

When adding or changing an endpoint:

1. Keep resources thin and call application/adapter code.
2. Preserve JSON-safe values and the `{data, meta, errors}` envelope.
3. Add/adjust the TypeScript interface in `frontend/src/lib/types/api.ts`.
4. Update `docs/FALCON_API_CONTRACT.md` and `docs/API.md`.
5. Update verification coverage.
6. Run API verification, frontend checks and a production build.

## Database changes

Schema changes require a deliberate migration or builder update. Update both JSON and CSV build paths if they must produce the same canonical schema. Never depend on a scraper repository import to serve data.

## Data changes

The web repository consumes external artifacts through environment variables. Do not add scrapers, raw retailer datasets, cookie factories or TÜİK calculator code here.

## Boundaries

- Domain/application/adapters do not import Falcon.
- API modules do not import frontend code or directly use `sqlite3`.
- Frontend code only accesses data through HTTP.
- Legacy Streamlit planning documents are historical and live under `docs/archive/`.
