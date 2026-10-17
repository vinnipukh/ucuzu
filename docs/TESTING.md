# Testing and Verification

## Unit tests

Install and run commands are in [GETTING-STARTED.md](GETTING-STARTED.md) (`uv sync --extra dev`, then `uv run pytest`).

Pytest suite under `tests/` for the pure domain and application logic (`domain/prices.py`, `application/use_cases.py`). Uses small in-memory DataFrames; no database or API server required. Runs in well under a second.

## Backend

`scripts/verify_falcon_api.py` (command in [GETTING-STARTED.md](GETTING-STARTED.md)) checks route/source contracts, stable envelopes, JSON-native serialization, import boundaries and bounded endpoint behavior.

## Frontend

`npm run check` and `npm run build` in `frontend/` (commands in [GETTING-STARTED.md](GETTING-STARTED.md#before-committing)). `npm run check` must complete without errors or warnings. `npm run build` creates the static SPA in `frontend/build/`.

## Database

```bash
uv run python scripts/test_sqlite_adapter.py
uv run python scripts/test_new_endpoints.py
```

These require a populated SQLite database configured through `PRICES_DB_PATH` or the default `data/prices.db`.

## Load testing

```bash
uv run python scripts/benchmark_falcon_api.py
uv run python scripts/benchmark_concurrent_api.py --concurrency 100
```

Use a disposable test database/snapshot. Do not benchmark against a production database while it is being rebuilt.

## End-to-end manual check

1. Start Falcon with `scripts/run_falcon_server.py`.
2. Build/preview the Svelte application.
3. Verify inventory loads and Gurmar is selected by default.
4. Exercise all five views, filters, search, themes and error states.
5. Stop and restart the API to confirm no frontend state is required for recovery.
