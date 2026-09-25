# Conventions

## API

- Every response uses `{data, meta, errors}`.
- Serialized values must be JSON-native; no pandas/numpy scalars, `NaN` or `NaT`.
- Invalid filters return descriptive 4xx envelopes.
- Database access belongs in adapters.
- Resources remain thin and delegate to application use cases.

## Frontend

- Svelte 5 runes are the state model.
- The SPA is static/client-only; it does not scan data files.
- All server data access goes through `frontend/src/lib/api/client.ts`.
- TypeScript contracts and `docs/FALCON_API_CONTRACT.md` change together.

## Database

- The serving database is generated and gitignored.
- Production API connections are read-only.
- Schema and index changes update builder/migration tooling and `docs/DATABASE.md`.
- Raw data and inflation source code do not move into this repository.

## Documentation

- Current setup lives directly under `docs/`.
- Dated research is under `docs/research/`.
- Monorepo and Streamlit history is under `docs/archive/` and must be labeled historical.
