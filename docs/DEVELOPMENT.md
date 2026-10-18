# Development

Checklists of files that must change together. Install, build and run commands are in [GETTING-STARTED.md](GETTING-STARTED.md); where code belongs and the layer rules are in [ARCHITECTURE.md](ARCHITECTURE.md).

Data is committed under `data/` (see [AGENTS.md](../AGENTS.md) and [DATA_CONTRACT.md](DATA_CONTRACT.md)). Environment variables such as `PRICES_DB_PATH` and `EPEYKATFG_MONTHLY_CSV` only override the default paths into that tree ([CONFIGURATION.md](CONFIGURATION.md)).

Every change: `uv run pytest` and `npm run check` (in `frontend/`) pass before committing.

## API endpoint change

Adding, removing or changing a route, parameter, response field, error code or header:

- [ ] The resource in `inflation_dashboard/api/resources.py` (and the route in `inflation_dashboard/api/falcon_app.py` for a new path). Keep it thin: logic goes in `application/`, database access in `adapters/sqlite_price_repository.py` (catalog routes: `adapters/sqlite_catalog_repository.py`).
- [ ] Values stay JSON-native and inside the `{data, meta, errors}` envelope.
- [ ] [FALCON_API_CONTRACT.md](FALCON_API_CONTRACT.md): the endpoint section, the error-code table if codes changed, and §6 (copy of `api.ts`) if types changed.
- [ ] `frontend/src/lib/types/api.ts`: the TypeScript types the SPA uses.
- [ ] [API.md](API.md): the endpoint table row.
- [ ] `scripts/verify_falcon_api.py`: route list, response-key tokens and endpoint smoke checks.
- [ ] Tests in `tests/` for new behaviour (`tests/test_api.py` uses `falcon.testing.TestClient`).
- [ ] Run `uv run python scripts/verify_falcon_api.py` with a built database.

## Schema or data layout change

Changing tables, indexes, views, retailer labelling, accepted file formats, header aliases or folder layout:

- [ ] `scripts/build_database.py`.
- [ ] `tests/test_build_database.py`, in the same commit.
- [ ] [DATABASE.md](DATABASE.md): pipeline, label rules, aliases, skip reasons, schema and indexes.
- [ ] [DATA_CONTRACT.md](DATA_CONTRACT.md): input layout and formats.
- [ ] `inflation_dashboard/adapters/sqlite_price_repository.py` if the views it queries change.
- [ ] Rebuild the database and run `uv run python scripts/verify_falcon_api.py` and `uv run python scripts/test_sqlite_adapter.py` against it.

## Data update

Copying new scraper output into `data/raw`, `data/prices_json` or `data/inflation`:

- [ ] Copy the files (new files only; commands in [SETUP.md](SETUP.md#4-take-new-csvs-from-inflationresearchstudy)) and record the source commits of the data repository in the commit message.
- [ ] `uv run python scripts/data_files.py check`. No committed file may exceed **85 MB**.
- [ ] For each oversized file, either `uv run python scripts/data_files.py split` (commits 80 MB `.partNNN` chunks and lists the original in the managed `.gitignore` block) or add it to `.gitignore`.
- [ ] Never commit `*.db`, `*.db-wal`, `*.db-shm`, `.env`, cookies or browser profiles.
- [ ] Commit and push in batches of about **500 MB**, so no single push approaches GitHub's 2 GB limit.
- [ ] Rebuild the database and check the build summary's skip counts for new retailers.
- [ ] If the new data needs a new folder rule or header alias, follow the schema/data layout checklist above.

## Frontend change

- [ ] `cd frontend && npm run check` passes with no errors **and no warnings**.
- [ ] `npm run build` succeeds.
- [ ] [USER_GUIDE.md](USER_GUIDE.md) if anything a user sees changed (controls, defaults, views).
- [ ] [frontend/README.md](../frontend/README.md) if state, defaults or source layout changed.
- [ ] Server data still goes only through `frontend/src/lib/api/client.ts`; any type change also follows the API checklist.
- [ ] Try the change in `npm run dev` against a running API.

## Configuration change

- [ ] [CONFIGURATION.md](CONFIGURATION.md): variable or flag row (default, read by, effect).
- [ ] `.env.example` or `frontend/.env.example`.
- [ ] `scripts/run_falcon_server.py --help` text if a launcher flag changed.

## Known code defects

Defects that are documented rather than fixed are listed in [ARCHITECTURE.md § Known issues](ARCHITECTURE.md#known-issues). Fixing one: remove its row there and update the docs that describe the old behaviour.
