# PRD: Documentation Consolidation and Accuracy Pass

## Introduction

The repository has 16 top-level files in `docs/` plus `README.md`, `AGENTS.md` and `frontend/README.md`. Over time the same content (setup commands, source layout, boundary rules) has been copied into four to six places. Recent changes made several of those copies wrong:

- the ASGI app was removed (WSGI only);
- the serving database was normalized (5 tables + 3 views);
- the data is now committed under `data/`;
- the frontend now loads retailers one category at a time.

This work restructures `docs/` so that each topic has **one** owning file. It corrects every statement that no longer matches the code, and adds docstrings and TSDoc to undocumented public code.

The audience is **developers and AI coding agents** who set up, change and review this repository.

### Scope: code changes allowed

Code, CI and config changes are in scope. All stories form a single list, and the [Implementation order](#implementation-order) below sets their priority. The code-fix stories (US-020 to US-027) fix the defects found during the audit ([Appendix A](#appendix-a-code-defects-found-during-the-audit)). They come early in the order so that later doc stories describe the fixed behaviour.

**Known issues rule:** when an acceptance criterion says "listed under Known issues", check the defect's fix story:
- if the fix story is done, document the **fixed** behaviour and do not list the defect;
- if the defect is marked "doc-only" in Appendix A, document the current behaviour and list it under Known issues.

**Tests:** no tests that check docs against code (no link checkers, no contract-vs-route tests). Ordinary unit tests for the code-fix stories are expected.

### Implementation order

Each story is completed in turn, in this order (priority 1 = first):

| Priority | Story | Priority | Story |
|---|---|---|---|
| 1 | US-020 Fix CI | 15 | US-008 Contract: envelope, errors, endpoints |
| 2 | US-025 Ignore staging files | 16 | US-009 Contract TypeScript sync |
| 3 | US-021 Launcher respects `PRICES_DB_PATH` | 17 | US-007 Reduce API.md |
| 4 | US-023 Remove dead launcher options | 18 | US-003 GETTING-STARTED |
| 5 | US-022 Remove CSV fallback | 19 | US-004 README |
| 6 | US-026 Single retailer constants | 20 | US-006 DEVELOPMENT checklists |
| 7 | US-024 Error envelope, no leaked text | 21 | US-013 USER_GUIDE / TESTING / frontend README |
| 8 | US-027 Same-origin `/api` | 22 | US-014 Docstrings: API layer |
| 9 | US-001 Docs index, archive SEPARATION | 23 | US-015 Docstrings: domain/application/adapters |
| 10 | US-002 Fix research links | 24 | US-016 Docstrings: scripts |
| 11 | US-005 ARCHITECTURE consolidation | 25 | US-017 TSDoc: lib and types |
| 12 | US-010 CONFIGURATION | 26 | US-018 Svelte `@component` blocks |
| 13 | US-011 DATABASE | 27 | US-019 AGENTS.md final pass |
| 14 | US-012 DATA_CONTRACT | | |

## Goals

- Every topic has exactly one owning document. Other files link to it instead of repeating it.
- Every command, CLI flag, endpoint, query parameter, response field, environment variable, default value, path and version in the docs has been manually checked against the current code.
- All known discrepancies listed in this PRD are corrected (see each story).
- Every public Python function, class and module in `inflation_dashboard/` and `scripts/` has a docstring.
- Every exported TypeScript type and function in `frontend/src/lib/` has TSDoc, and every `.svelte` component has an `@component` block.
- Code defects found during the audit are fixed (US-020 to US-027). The ones marked doc-only are recorded in one "Known issues" list.
- No automated doc tests are added.

## Target structure

| File | Owns | Notes |
|---|---|---|
| `README.md` | Pitch, 5-line quickstart, links | Remove the duplicated layout, route list and command blocks |
| `AGENTS.md` | Hard rules for agents (repo boundary, data rules, change policy) | Keep the rules; replace the command blocks with links |
| `docs/README.md` | Index of every doc, including `research/`, `benchmarks/`, `archive/` | Links, not code spans |
| `docs/GETTING-STARTED.md` | **Only** place for install / build-DB / run / verify commands | Absorbs the setup parts of `DEVELOPMENT.md` |
| `docs/ARCHITECTURE.md` | Source layout, layer boundaries, request flow, Known issues | Absorbs `CONVENTIONS.md` and `CONCERNS.md` |
| `docs/DEVELOPMENT.md` | Change checklists (API change, DB/schema change, data update, frontend change) | Setup content removed |
| `docs/TESTING.md` | Test suite, verification scripts, manual QA | Kept |
| `docs/CONFIGURATION.md` | Every environment variable and launcher flag | Kept and expanded |
| `docs/DATA_CONTRACT.md` | `data/` layout and file formats | Kept |
| `docs/DATABASE.md` | Schema, indexes, build pipeline, runtime connection mode | Kept |
| `docs/FALCON_API_CONTRACT.md` | **Authoritative** API reference | Kept |
| `docs/API.md` | Endpoint table + link to the contract + performance notes | Reduced to a summary |
| `docs/USER_GUIDE.md` | End-user walkthrough of the SPA | Kept |
| `frontend/README.md` | Frontend-only state, env, source layout | Generic commands removed |
| `docs/SEPARATION.md` | — | Moved to `docs/archive/` with a "historical" banner |
| `docs/CONVENTIONS.md`, `docs/CONCERNS.md` | — | Content merged into `ARCHITECTURE.md`. Each file is replaced by a one-line pointer, or deleted if no inbound links remain |

## User Stories

### US-001: Restructure the docs index and move historical files
**Description:** As a new contributor, I want one index that links every doc so that I can find the owning file for any topic.

**Acceptance Criteria:**
- [ ] `docs/SEPARATION.md` is moved to `docs/archive/SEPARATION.md` with a top banner: "Historical: describes the 2026 extraction from the monorepo; not current setup guidance."
- [ ] `docs/README.md` links (markdown links, not code spans) every file in `docs/`, `docs/research/` (all three notes listed individually), `docs/benchmarks/` and `docs/db_benchmark_results.json`, plus `docs/archive/`.
- [ ] Each entry in `docs/README.md` has a one-line description of what that file owns, matching the Target structure table.
- [ ] The claim "database research" under `research/` is corrected to describe the actual contents (Falcon optimization, profiling/DB caching, benchmark case studies).
- [ ] Every relative link in `docs/README.md` resolves to an existing file (checked by hand).

### US-002: Fix broken links inside research and report docs
**Description:** As a reader of the optimization reports, I want their links to work so that I can follow the cited research.

**Acceptance Criteria:**
- [ ] `docs/FALCON-API-OPTIMIZATION-REPORT-2026-09-03.md:9,12` point to `docs/research/research-notes-*.md`.
- [ ] That report's reference to `scripts/precompute_artifacts.py` (line ~102) is marked "(removed; never existed in this repository)" or reworded. The report text is not otherwise rewritten.
- [ ] `docs/FALCON-DEPLOYMENT-TUNING-RESEARCH.md:99` and `docs/research/falcon-benchmarks-case-studies.md:122` point to `docs/archive/monorepo/TECH-STACK-SEARCH.md`.
- [ ] `docs/research/research-notes-falcon-framework-optimization.md:9,262` point to `docs/research/research-notes-profiling-db-caching-falcon.md`.
- [ ] Dated reports keep their original findings. Only paths are changed.

### US-003: Make GETTING-STARTED the single setup guide
**Description:** As a new developer, I want one page that takes me from `git clone` to a running API and SPA so that I don't have to reconcile several conflicting command lists.

**Acceptance Criteria:**
- [ ] Prerequisites state Python `>=3.14` (from `pyproject.toml`), uv and npm. For Node.js they state **24 LTS recommended**, `>=22.12` minimum (vite 8 needs `^20.19 || >=22.12`; Node 20 is end-of-life).
- [ ] The prerequisite "a data artifact from the separate repo" is removed. The page states that the data is committed under `data/` (`raw/`, `prices_json/`, `inflation/`).
- [ ] The install step uses `uv sync --extra dev` (pytest lives in the `dev` extra), not bare `uv sync`.
- [ ] Includes the steps in order:
  - `uv run python scripts/data_files.py join`, explained as rebuilding split files such as `data/raw/EpeyKatfg/series.csv`;
  - `scripts/build_database.py`;
  - `pytest`;
  - `verify_falcon_api.py`;
  - running the API;
  - `npm install` / `npm run dev`.
- [ ] States the API connection model (after US-027):
  - an empty `VITE_API_BASE_URL` makes the SPA call same-origin `/api`;
  - in development the Vite proxy forwards that to `:8000`;
  - in production either serve the static build and the API behind one reverse proxy that routes `/api`, or set `VITE_API_BASE_URL` at build time and allow the SPA's origin in `FALCON_CORS_ORIGINS`.
- [ ] Includes a minimal reverse-proxy example (nginx or Caddy, about 10 lines) that serves `frontend/build` with an `index.html` fallback and proxies `/api` to the Falcon server.
- [ ] Every command on the page was run (or `--help` checked) against the current repo during this work, and the results noted in the PR description.
- [ ] Setup commands are removed from `DEVELOPMENT.md`, `TESTING.md` and `frontend/README.md` and replaced with links to this page. `README.md` keeps only a quickstart of at most 5 commands. `AGENTS.md`'s "Development" section links here. Agents may keep a compact command list there, but it must be identical to this page.

### US-004: Shrink README.md to pitch + quickstart
**Description:** As a visitor to the repo, I want a short README so that I understand what the project is and where to go next.

**Acceptance Criteria:**
- [ ] The repo is named consistently. `inflationstudymirror-web` / `cd inflationstudymirror-web` (lines ~17, ~35) are replaced with the real name and remote (`cimri-clone`, `github.com/vinnipukh/cimri-clone`), or the README explicitly says the project is published under that name.
- [ ] The data-repository reference matches `AGENTS.md`: name both `vinnipukh/inflationstudymirror` (mirror) and `urazkagangunes/InflationResearchStudy` (upstream), with the same wording in both files.
- [ ] Removes "SQLite, CSV and async repositories". Only the SQLite and CSV adapters exist.
- [ ] The source layout, the 9-route list and the full command blocks are removed and replaced with links to `ARCHITECTURE.md`, `FALCON_API_CONTRACT.md` and `GETTING-STARTED.md`.
- [ ] README is at most ~60 lines.

### US-005: Consolidate ARCHITECTURE.md (absorb CONVENTIONS and CONCERNS)
**Description:** As a developer changing code, I want one place that describes layout, boundaries and known issues so that I know where code belongs and what is fragile.

**Acceptance Criteria:**
- [ ] `ARCHITECTURE.md` contains:
  - the source layout (including `frontend/src` top level);
  - layer boundaries (domain/application/adapters independent of Falcon; no `sqlite3` in `api/`);
  - the request flow (SPA → Falcon WSGI → filters/cache → SQLite adapter, CSV fallback);
  - coding conventions from `CONVENTIONS.md`.
- [ ] Removes "The repository does not contain the raw data" (from `CONCERNS.md:5`). `data/raw` is committed.
- [ ] Adds a **Known issues** section listing every Appendix A item marked doc-only, plus any fix story not completed, each with file:line and one sentence of impact.
- [ ] `CONVENTIONS.md` and `CONCERNS.md` are removed or reduced to a one-line pointer. All inbound links (grep `CONVENTIONS.md`, `CONCERNS.md`) are updated.
- [ ] The boundary rules are stated in full only here. `AGENTS.md` keeps its short rule list and links here for details.

### US-006: Rewrite DEVELOPMENT.md as change checklists
**Description:** As a contributor making a change, I want a checklist per change type so that I update every file that must change together.

**Acceptance Criteria:**
- [ ] Contains checklists for:
  - (a) API endpoint change: the resource, `FALCON_API_CONTRACT.md`, `frontend/src/lib/types/api.ts`, `API.md` table, `verify_falcon_api.py`;
  - (b) schema/data layout change: `build_database.py`, `tests/test_build_database.py`, `DATABASE.md`, `DATA_CONTRACT.md`;
  - (c) data update: `data_files.py check`/`split`, 85 MB limit, ~500 MB push batches;
  - (d) frontend change: `npm run check`, `USER_GUIDE.md` if the UI changed.
- [ ] Removes the claim (line ~55) that the app "consumes external artifacts through environment variables. Do not add … raw retailer datasets". Replaced with: data is committed under `data/` per `AGENTS.md`, and the env vars only override the default paths.
- [ ] Removes "async repositories" (line ~12).
- [ ] Contains no setup commands (links to `GETTING-STARTED.md`).

### US-007: Correct API.md and reduce it to a summary
**Description:** As an API consumer, I want the short API doc to agree with the contract so that I am not misled by an outdated summary.

**Acceptance Criteria:**
- [ ] `API.md` contains: one paragraph on the envelope, an endpoint table (method, path, purpose, key params), a link to `FALCON_API_CONTRACT.md` as authoritative, and the performance notes section (currently lines ~295–302).
- [ ] The performance notes no longer claim a "covering-index seek, <2 ms" for product search. They state that search does a substring match over the `product_prices` view (`sqlite_price_repository.py:~865`).
- [ ] The duplicated per-endpoint sections and examples are removed. Before removal, any content that is correct and **missing** from the contract (the product-detail response example) is moved into the contract (see US-008).
- [ ] No text claims `meta` carries pagination limits or timestamps.

### US-008: Correct FALCON_API_CONTRACT.md: envelope, errors and endpoints
**Description:** As an API consumer, I want the contract to describe exactly what the server returns so that I can rely on it.

**Acceptance Criteria:**
- [ ] Default retailers read Gurmar, Vakko, HomeGoods (`csv_price_repository.py:33-37`), not "yapimaks".
- [ ] Error objects are documented as `{code, message}` only, with `meta` on the envelope (`serialization.py:202-205`).
- [ ] The error code list matches codes the server actually emits (grep `code=` / error builders in `inflation_dashboard/api/`). `bad_request` and the 160-character message cap are removed.
- [ ] Documents that `server_error` messages contain the raw exception text (`resources.py:~332,~385`), and lists this under Known issues.
- [ ] Documents that unknown routes (404) and unhandled 500s return Falcon's default `{"title": …}` body, not the envelope. Documents that only `/api/products/search` and `/api/product` wrap exceptions into `server_error`.
- [ ] Inventory: timestamps are full ISO datetimes (`…T00:00:00`), and `file_count` is in `meta`.
- [ ] Product search: out-of-range `limit` returns HTTP 400 `invalid_filter`. It is not clamped.
- [ ] Product detail: documents the `history` array and includes a response example. Also documents that `product_name` is ignored when `product_id` is given (`resources.py:~347`).
- [ ] Retailer averages documents the duplicate `retailer_averages` key. Coverage documents `skipped_files`.
- [ ] Documents meta warnings: "history response may be large" (`resources.py:~192`) and "selected files skipped; no usable rows loaded" (`filters.py:~441`).
- [ ] Adds a **Caching & compression** section:
  - strong ETag;
  - `If-None-Match` → 304;
  - `Cache-Control: public, max-age=300`;
  - gzip for payloads ≥1 KB with `Vary: Accept-Encoding` (`resources.py:84-145`, `filters.py:212-240`).
- [ ] "Last Updated" is set to the date of this change.

### US-009: Sync the contract's TypeScript section with `frontend/src/lib/types/api.ts`
**Description:** As a frontend developer, I want the contract's TypeScript block to match the real types file so that I know what the client expects.

**Acceptance Criteria:**
- [ ] The TypeScript section (§5) is changed from "what api.ts should contain" to "mirrors api.ts as of <date>", and is regenerated from the real file. Alternatively, it is replaced with a link plus a list of differences between server output and client types.
- [ ] `MonthlyInflationRecord` includes `pct_increased`, `pct_decreased` and `pct_unchanged`.
- [ ] Documents the differences between client types and server output without changing `api.ts`:
  - `ProductSearch*` and `ProductHistoryRecord` have no client types because the SPA never calls `/api/products/search`;
  - `InventoryMeta.warnings` exists in the client but is never sent by the server;
  - `ProductDetailMeta` fields are `string|null`.
- [ ] The client example (§ ~788–854) is replaced with an accurate description of `frontend/src/lib/api/client.ts`:
  - the base URL comes from the filters store;
  - the extra `network_error` and `bad_response` codes;
  - it returns `{data, meta}`.

### US-010: Correct and complete CONFIGURATION.md
**Description:** As an operator, I want every environment variable and launcher flag documented with its real effect so that configuration does what I expect.

**Acceptance Criteria:**
- [ ] States that **no `.env` file is loaded** (no dotenv). `.env.example` values must be exported into the environment. Notes that `.env.example`'s `FALCON_CORS_ORIGINS=http://localhost:5173` differs from the code default `*`.
- [ ] States that `scripts/run_falcon_server.py` **overwrites** `PRICES_DB_PATH` with its `--sqlite-db` value (default `data/prices.db`, `run_falcon_server.py:85,266`). Use `--sqlite-db` with the launcher; `PRICES_DB_PATH` only applies when the WSGI app is served by other means. Listed under Known issues.
- [ ] Documents the launcher env vars `HOST` (127.0.0.1), `PORT` (8000), `WEB_CONCURRENCY`, `SERVER_THREADS` (8) and `SERVER_BACKLOG` (2048) (`run_falcon_server.py:232-256`), and all CLI flags (`--engine granian|gunicorn|waitress`, `--workers`, `--threads`, `--port`, `--sqlite-db`, `--no-sqlite-readonly`).
- [ ] Documents that `--no-sqlite-readonly` and the exported `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS` and `SQLITE_URI` have no effect: request connections are always `mode=ro`. Listed under Known issues.
- [ ] `FALCON_TIMING_LOG` lists its accepted truthy values (`1`, `true`, `yes`, `on`).
- [ ] States that a relative `PRICES_DB_PATH` resolves against the current working directory. `INFLATION_DATA_ROOT` is removed from the table (US-022).
- [ ] Each variable row lists: name, default (verified in code), read by (file:line), effect.

### US-011: Correct DATABASE.md
**Description:** As a developer changing the build, I want the database doc to match `build_database.py` exactly so that I can reason about schema and ingestion.

**Acceptance Criteria:**
- [ ] Lists the 4 indexes: `idx_products_retailer_name`, `idx_products_name`, `idx_products_product_id`, `idx_sources_retailer_date` (`build_database.py:124-129`).
- [ ] Group-label rules match the code:
  - a group with a store sub-folder converts `_` to a space; a group without one keeps the underscore (`:178` vs `:181`);
  - non-TÜİK top-level folders (e.g. `EpeyKatfg`) are labelled by joining folder names (`:176`);
  - the `Health_Diagnostic_Surgical_Services` stem alias is documented.
- [ ] The column-alias list is complete (adds `urunismi`, `productname`, `productcost`, `normalprice`, `regularprice`, per `:64-68`).
- [ ] Skip reasons add "no usable rows" and "unparseable".
- [ ] Documents the build lifecycle:
  - staging into `<db>.building`;
  - the `os.replace` swap;
  - removal of stale `-wal`/`-shm` files;
  - the final database left in WAL mode.

  Notes under Known issues that `*.db.staging` is not covered by `.gitignore`.
- [ ] Documents the JSON fallback:
  - JSON is used only for retailers with no successfully ingested CSV;
  - only `name`, `category` and `prices` are read, and `latest_price`/`min_price`/`max_price` are recomputed;
  - `EpeyKatfg` and `Technology` come only from `prices_json` (their raw files have no date in the name).
- [ ] Replaces "the web process does not require write access" (line ~62) with the real behaviour: the launcher opens the DB read-write once at startup to set `journal_mode=WAL` if needed (`run_falcon_server.py:64-80`). Request connections are `mode=ro` with `synchronous=NORMAL` and `temp_store=MEMORY`.
- [ ] Documents that when the DB is missing or empty, data endpoints return 503 `database_unavailable` (US-022).

### US-012: Correct DATA_CONTRACT.md
**Description:** As a data maintainer, I want the data contract to match what the build and the CSV fallback actually accept.

**Acceptance Criteria:**
- [ ] Delimiters: comma, semicolon **and tab**. Encoding: UTF-8 with cp1254 fallback (build only).
- [ ] No longer calls the CSV reader "the shared reader" (line ~69). States that `scripts/build_database.py` is the only reader of `data/raw`.
- [ ] Every mention of the runtime CSV fallback and `INFLATION_DATA_ROOT` is removed (removed in US-022). This covers `DATA_CONTRACT.md:~9,~39,~69`, `ARCHITECTURE.md:~32`, `GETTING-STARTED.md:~64`, `API.md:~5,~301` and `FALCON_API_CONTRACT.md:~23`. Troubleshooting says that a missing DB gives 503 `database_unavailable` and that the fix is to run `build_database.py`.
- [ ] Documents `data_files.py`:
  - 80 MB chunks vs the 85 MB limit;
  - `.partNNN` naming;
  - re-splitting removes stale parts;
  - the managed `.gitignore` block;
  - `join` skips an original that is already intact;
  - `check` uses `git check-ignore`;
  - the `--data-dir` option;
  - the file currently split (`data/raw/EpeyKatfg/series.csv`).
- [ ] JSON section states which fields the build reads (see US-011).

### US-013: Correct USER_GUIDE.md, TESTING.md and frontend/README.md for category-based loading
**Description:** As a dashboard user, I want the guide to describe what I actually see so that I can use the category selector and settings.

**Acceptance Criteria:**
- [ ] `USER_GUIDE.md`:
  - replaces "Every retailer in the inventory is selected by default" with category-based selection (default `Markets`, or the last category remembered in localStorage);
  - documents the Category field (`Sidebar.svelte:~112`);
  - documents the API settings / Load settings sections;
  - documents the Auto/Light/Dark theme toggle (`Header.svelte`).
- [ ] `TESTING.md:~52` replaces "Gurmar is selected by default". `TESTING.md:~12` lists `tests/test_build_database.py` alongside the domain/application tests.
- [ ] `frontend/README.md`:
  - replaces "Gurmar is selected by default" and "file cap defaults to 45; all-history sends 0" with the real defaults (`DEFAULT_CATEGORY`, `DEFAULT_ALL_HISTORY = true` → `max_files=0`);
  - describes the empty-`VITE_API_BASE_URL` → same-origin behaviour from US-027 and links to the deployment notes in US-003;
  - adds `themes.svelte.ts`, `routes/+layout.svelte` and `lib/index.ts` to the source layout.
- [ ] `SEPARATION.md` (now archived) is not edited beyond the banner. Its stale claims (ignored `data/`, "three canonical tables") are covered by the banner.
- [ ] Verify in the browser using the dev-browser skill that every UI element named in `USER_GUIDE.md` exists, with the stated defaults, in `npm run dev` against a locally built DB.

### US-014: Docstrings for the Falcon API layer
**Description:** As a developer reading `inflation_dashboard/api/`, I want each module and resource documented so that I understand the HTTP layer without reading every line.

**Acceptance Criteria:**
- [ ] Module docstrings added to `falcon_app.py`, `resources.py`, `filters.py` and `serialization.py`.
- [ ] Docstrings added to:
  - `_cors_middleware`, `process_request` and `process_response`;
  - the 6 resource classes (Health, Inventory, History, RetailerAverages, Movers, Coverage) and every `on_get`, naming the route, its params and its response;
  - `_set_filter_error`, `_single_selected_retailer` and `_parse_bounded_int`;
  - `ParsedFilters`, `parse_bool_param` and `clear_response_cache`.
- [ ] Docstrings describe current behaviour, including the quirks in Appendix A where relevant.
- [ ] This story's own diff contains only docstring/comment lines (checked by hand).
- [ ] `uv run pytest` and `uv run python scripts/verify_falcon_api.py` pass.

### US-015: Docstrings for domain, application and adapters
**Description:** As a developer, I want the core logic documented so that I can change it safely.

**Acceptance Criteria:**
- [ ] Module docstrings plus docstrings on all public functions in:
  - `domain/prices.py` (`parse_date_from_name`, `coerce_price`, `first_non_empty_column`, `build_product_frame`);
  - `application/chart_specs.py` (4);
  - `application/use_cases.py` (8);
  - `adapters/csv_price_repository.py` (`detect_retailer`, `discover_csv_inventory`, `load_price_history`).
- [ ] `detect_retailer`'s docstring states the `Datas` path requirement.
- [ ] A comment marks the duplicated `SUPPORTED_RETAILERS` / `DEFAULT_RETAILERS` constants (unused in `sqlite_price_repository.py:33-52`, authoritative in `csv_price_repository.py`).
- [ ] Only docstring/comment lines change. `uv run pytest` passes.

### US-016: Docstrings for scripts
**Description:** As a maintainer running scripts, I want each script and its functions documented so that `--help` and the source explain them.

**Acceptance Criteria:**
- [ ] Every public function has a docstring in:
  - `scripts/build_database.py` (`discover_raw_csvs`, `Loader.add`, `Loader.finish`, `ingest_raw`, `ingest_json_fallback`, `build`, `main`);
  - `scripts/data_files.py` (`split`, `join`, `check`, `main`, plus a module docstring);
  - `scripts/verify_falcon_api.py`;
  - `scripts/test_sqlite_adapter.py`;
  - `scripts/run_falcon_server.py` (`main`);
  - `scripts/benchmark_falcon_api.py` (module docstring).
- [ ] `scripts/benchmark_db_queries.py` and `benchmark_concurrent_api.py`: module docstring plus docstrings on entry points and any function longer than ~10 lines. Trivial helpers may be skipped.
- [ ] Only docstring/comment lines change. `--help` output for each script is unchanged unless the docstring feeds `argparse` `description`. If it does, the change is noted in the PR.

### US-017: TSDoc for frontend lib and types
**Description:** As a frontend developer, I want exported types and functions documented so that the editor shows what each one means.

**Acceptance Criteria:**
- [ ] Every exported interface/type in `frontend/src/lib/types/api.ts` (~40) has a TSDoc block naming the endpoint it models. Fields that differ from server output carry a note (see US-009).
- [ ] Every export in these files has TSDoc:
  - `themes.svelte.ts` (5);
  - `chartOptions.svelte.ts` (7);
  - `format.ts`, `search.ts`, `chartTheme.svelte.ts`, `filters.svelte.ts` and `client.ts` (the remaining undocumented exports, including `ApiErrorResponse`).
- [ ] Only comment lines change. `npm run check` and `npm run build` pass with no new warnings.

### US-018: Component docs for Svelte files
**Description:** As a frontend developer, I want each component to say what it renders and which stores and props it uses.

**Acceptance Criteria:**
- [ ] All 16 `.svelte` files (9 components, 5 views, 2 routes) have an `<!-- @component ... -->` block. The block gives a one-paragraph purpose, the props, the stores it reads or writes, and the API endpoints it triggers.
- [ ] Only comment lines change. `npm run check` passes.
- [ ] Verify in the browser using the dev-browser skill that the app renders exactly as before (spot-check all 5 views).

### US-019: Final consistency pass on AGENTS.md
**Description:** As an AI agent, I want `AGENTS.md` to be short, correct and linked to the owning docs so that I follow the current rules.

**Acceptance Criteria:**
- [ ] The rule sections (Repository boundary, Data rules, Architecture boundaries, Change policy) are kept. The data-repo reference matches README (US-004).
- [ ] Each rule section links to its owning doc (`DATA_CONTRACT.md`, `DATABASE.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`).
- [ ] The Development command block matches `GETTING-STARTED.md` exactly (including `data_files.py join`).
- [ ] Adds a pointer: "Known code defects are listed in `docs/ARCHITECTURE.md#known-issues`; do not assume documented behaviour that is listed there."

## Functional Requirements

- FR-1: Each topic in the Target structure table must be fully described in exactly one file. Any other file mentioning the topic must link to that file rather than restate it, except `AGENTS.md`'s command block (FR-6).
- FR-2: Every factual statement edited or kept in the in-scope docs must be checked against the code. In-scope means everything except `docs/archive/`, `docs/research/`, the dated `FALCON-*` reports and the benchmark JSON. "Checked" means the author read the cited code or ran the command.
- FR-3: Any statement that is true of the code but describes a defect must be written as current behaviour and added to the Known issues list in `ARCHITECTURE.md`.
- FR-4: Dated reports and research notes may only have their paths/links corrected (US-002). Their findings must not be rewritten.
- FR-5: Behaviour changes may only be made in the code-fix stories (US-020 to US-027). The inline-doc stories (US-014 to US-018) must change only docstrings, TSDoc/JSDoc blocks, `@component` blocks or comments in `.py`, `.ts` and `.svelte` files.
- FR-9: Stories are implemented in the order given in [Implementation order](#implementation-order).
- FR-6: `AGENTS.md` may keep a compact command list, but it must be byte-for-byte identical to the corresponding commands in `GETTING-STARTED.md`.
- FR-7: Every relative markdown link in in-scope docs must resolve to an existing file and, where an anchor is given, an existing heading. This is checked manually, not with an automated test.
- FR-8: When a file is removed or moved, every inbound reference in the repo must be updated (grep the filename).

## Non-Goals (Out of Scope)

- **No doc-checking tests:** no tests that check docs against code, no link checkers and no contract-vs-route tests. Unit tests for the code-fix stories are allowed.
- No fixes for the Appendix A items marked doc-only (A8, A11). They are documented instead.
- No new runtime dependencies (e.g. no `python-dotenv`).
- No generated docs site (MkDocs etc.) and no OpenAPI spec.
- No rewriting of `docs/archive/`, `docs/research/` or the dated `FALCON-*` reports beyond link fixes.
- No end-user marketing or tutorial content beyond `USER_GUIDE.md`.

## Technical Considerations

- Line numbers in this PRD come from an audit on 2026-10-17 against commit `134f0a0`. Re-locate each one by content before editing.
- Docstring changes to `argparse`-based scripts can change `--help` if the module docstring is passed as `description`. Check each script.
- Adding `<!-- @component -->` blocks in Svelte 5 must not trigger `svelte-check` warnings.
- Use the dev-browser skill with a locally built `data/prices.db` (`uv run python scripts/build_database.py`, ~1.4 GB) for the UI verification steps.

## Success Metrics

- All discrepancies listed in US-002 to US-013 are resolved (each acceptance criterion checked).
- Setup commands appear in exactly one doc plus the identical `AGENTS.md` block, down from 6 places.
- 100% of public Python functions/classes/modules in `inflation_dashboard/` and the scripts in scope have docstrings (up from roughly 0–50% per module).
- 100% of exported TS types/functions in `frontend/src/lib/` have TSDoc (up from ~7% of types and ~50% of functions), and all 16 Svelte files have `@component` blocks (up from 0).
- A reviewer following only `GETTING-STARTED.md` on a clean clone reaches a running API + SPA without consulting another file.

## Open Questions

- Should `CONVENTIONS.md` and `CONCERNS.md` be deleted outright, or kept as one-line pointer files so that old links keep working?
- Is `cimri-clone` the intended public name, or should the remote be renamed to `inflationstudymirror-web` to match the docs?
- Node: move CI and `.nvmrc` from 24 to 26 once Node 26 enters LTS (scheduled for late October 2026)?

## User stories: code fixes

(Listed here for readability; see [Implementation order](#implementation-order) for when each one runs.)

### US-020: Fix CI
**Description:** As a maintainer, I want CI to pass and run the tests so that regressions are caught.

**Acceptance Criteria:**
- [ ] The `scripts/verify_redis_store.py` step is removed from `.github/workflows/ci.yml`.
- [ ] CI runs `uv sync --extra dev` and `uv run pytest`.
- [ ] Node is pinned to `'24'` (current Active LTS).
- [ ] `frontend/package.json` gets `"engines": { "node": ">=22.12" }`, and `frontend/.nvmrc` contains `24`.
- [ ] CI still runs `npm ci`, `npm run check` and `npm run build`.
- [ ] Does not build the full database in CI unless it fits the runner's time and disk budget. `verify_falcon_api.py` may be skipped in CI, with that noted in `TESTING.md`.
- [ ] The workflow passes on a pushed branch, or `act`/YAML validation succeeds locally if pushing is not possible.

### US-021: Launcher respects `PRICES_DB_PATH`
**Description:** As an operator, I want `PRICES_DB_PATH` to select the database when I don't pass `--sqlite-db`.

**Acceptance Criteria:**
- [ ] `--sqlite-db` defaults to `os.environ.get("PRICES_DB_PATH")`, falling back to `data/prices.db`.
- [ ] Precedence is `--sqlite-db` > `PRICES_DB_PATH` > default. It is stated in the `--help` text.
- [ ] Unit test: with `PRICES_DB_PATH=/x.db` and no flag, the resolved path is `/x.db`.
- [ ] `uv run pytest` passes.

### US-022: Remove the runtime CSV fallback
**Description:** As a maintainer, I want the API to serve only from the SQLite database so that there is one data path to maintain. The database is always built from committed `data/`, so the fallback has no use.

**Acceptance Criteria:**
- [ ] `inflation_dashboard/adapters/csv_price_repository.py` is deleted.
- [ ] `inflation_dashboard/api/filters.py` no longer imports it. `get_inventory` and the history loader call only `sqlite_price_repository`.
- [ ] When the database is missing or empty, the API returns a clear error instead of silently falling back:
  - `/api/health` stays 200 and reports the database as unavailable;
  - data endpoints return 503 with code `database_unavailable` and message "Database not found; run scripts/build_database.py".
- [ ] `DEFAULT_RETAILERS` (and `SUPPORTED_RETAILERS` if still needed) move to a non-CSV module. See US-026.
- [ ] `INFLATION_DATA_ROOT` is removed from the code, `.env.example` and `AGENTS.md` (Data rules). Docs are handled in US-010 / US-012.
- [ ] `scripts/verify_falcon_api.py:~70` no longer checks for the `discover_csv_inventory` / `load_price_history` tokens.
- [ ] Docstrings and comments that mention the CSV module are updated: `sqlite_price_repository.py:~177,~232` ("parity with / drop-in replacement for csv_price_repository").
- [ ] `pandas` stays a dependency only if something else still uses it (checked with grep).
- [ ] Unit test: with `PRICES_DB_PATH` pointing to a missing file, `GET /api/inventory` returns 503 with `errors[0].code == "database_unavailable"`.
- [ ] `uv run pytest` and `uv run python scripts/verify_falcon_api.py` pass.

### US-023: Remove dead launcher SQLite options
**Description:** As an operator, I want launcher options that do nothing to be removed so that I am not misled.

**Acceptance Criteria:**
- [ ] The `--no-sqlite-readonly` flag is removed from `run_falcon_server.py`.
- [ ] The unused exports `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS` and `SQLITE_URI` are removed. The variables that are actually read (`SQLITE_BUSY_TIMEOUT`, `SQLITE_CACHE_SIZE`, `SQLITE_MMAP_SIZE`) are kept.
- [ ] Grep confirms nothing else in the repo (scripts, docs, CI) references the removed names, apart from docs updated in US-010.
- [ ] `uv run python scripts/run_falcon_server.py --help` works, and the server starts and serves `/api/health`.

### US-024: Envelope for 404 and 500, and no leaked exception text
**Description:** As an API consumer, I want every error, including unknown routes and crashes, to use the `{data, meta, errors}` envelope without exposing internals.

**Acceptance Criteria:**
- [ ] `create_app` registers handlers that render the envelope for `falcon.HTTPError` (including 404/405) and for unhandled `Exception` (500). The error codes are `not_found`, `method_not_allowed` and `server_error`.
- [ ] Unhandled exceptions are logged with a traceback server-side. The response message is a fixed string, e.g. `"Internal server error"`. The raw exception text is no longer sent, including from the existing catches in `/api/products/search` and `/api/product`.
- [ ] CORS headers are still present on error responses.
- [ ] Unit tests (Falcon `testing.TestClient`):
  - `GET /api/does-not-exist` → 404 with `errors[0].code == "not_found"`;
  - a resource forced to raise → 500 with `server_error` and no exception text in the body.
- [ ] `uv run pytest` and `uv run python scripts/verify_falcon_api.py` pass.

### US-025: Ignore build staging files
**Description:** As a maintainer, I want every temporary database build file ignored so that a crashed build cannot be committed.

**Acceptance Criteria:**
- [ ] `.gitignore` covers `*.db.staging*` in addition to `*.db.building*`. It is added outside the `data_files.py` managed block.
- [ ] `git check-ignore data/prices.db.staging` exits 0.

### US-026: Remove the duplicated retailer constants
**Description:** As a developer, I want one definition of supported and default retailers so that they can't drift apart.

**Acceptance Criteria:**
- [ ] The unused `SUPPORTED_RETAILERS` / `DEFAULT_RETAILERS` copies in `sqlite_price_repository.py:33-52` are removed (after grep confirms they are unused).
- [ ] `DEFAULT_RETAILERS` lives in one module (after US-022, not the CSV module). Each retailer in it exists in a freshly built `data/prices.db` (checked manually with `SELECT name FROM retailers`).
- [ ] `SUPPORTED_RETAILERS` is deleted if nothing uses it after US-022. Otherwise it is derived from the `retailers` table rather than hardcoded.
- [ ] `uv run pytest` and `verify_falcon_api.py` pass.

### US-027: Empty `VITE_API_BASE_URL` means same-origin `/api`
**Description:** As an operator, I want a build without `VITE_API_BASE_URL` to call the API on its own origin so that a forgotten env var doesn't make every visitor's browser call its own `localhost:8000`.

**Acceptance Criteria:**
- [ ] `DEFAULT_API_BASE_URL` in `frontend/src/lib/stores/filters.svelte.ts:~9` is `''` when `VITE_API_BASE_URL` is unset or blank. A non-empty value is still used with trailing slashes removed.
- [ ] `fetchApi` in `client.ts` builds a relative URL (`/api/...`) when the base is `''`. It does not produce `//api` or `undefined/api`.
- [ ] The sidebar's API settings field shows a placeholder such as "same origin (/api)" when the value is empty, and an explicit URL still overrides it at runtime.
- [ ] `frontend/.env.example` sets `VITE_API_BASE_URL=` (empty), and its comment describes same-origin as the default.
- [ ] The `vite.config.ts` proxy comment is accurate. The proxy `/api` → `http://localhost:8000` is kept.
- [ ] `npm run check` and `npm run build` pass.
- [ ] Verify in the browser using the dev-browser skill:
  - with `npm run dev` and no `.env`, all 5 views load data;
  - the browser network tab shows requests to `http://localhost:5173/api/...`, served through the proxy.
- [ ] `npm run preview` without a proxy shows an API error state (not a blank page). This is expected and is documented in US-003 / US-013.

## Appendix A: Code defects found during the audit

| # | Defect | Location | Handling |
|---|---|---|---|
| A1 | CI runs `scripts/verify_redis_store.py`, which does not exist. CI never runs `pytest`. CI pins Node `'20'` (vite 8 needs ≥20.19) | `.github/workflows/ci.yml:35,39` | Fixed by US-020 |
| A2 | The launcher overwrites `PRICES_DB_PATH` with `--sqlite-db` (default `data/prices.db`) | `scripts/run_falcon_server.py:85,266` | Fixed by US-021 |
| A3 | The runtime CSV fallback finds no files in the committed `data/raw` layout (requires a `Datas` path component; supported-retailer list is stale) | `adapters/csv_price_repository.py:18-31,90-100` | Removed by US-022 |
| A4 | `--no-sqlite-readonly` and the exported `SQLITE_*` env vars are never read | `scripts/run_falcon_server.py:87-94,270` | Fixed by US-023 |
| A5 | 404 and unhandled 500 responses are not wrapped in the envelope; only 2 endpoints catch exceptions | `api/falcon_app.py`, `api/resources.py` | Fixed by US-024 |
| A6 | `server_error` returns the raw exception text to clients | `api/resources.py:~332,~385` | Fixed by US-024 |
| A7 | The SPA ignores the same-origin `/api` proxy when `VITE_API_BASE_URL` is empty and calls `http://localhost:8000` instead | `frontend/src/lib/stores/filters.svelte.ts:9`, `client.ts:49` | Fixed by US-027 |
| A8 | `.env.example` exists but nothing loads `.env` | repo-wide (no dotenv) | **Doc-only** (US-010 says values must be exported) |
| A9 | `*.db.staging` is not in `.gitignore` | `.gitignore` | Fixed by US-025 |
| A10 | `SUPPORTED_RETAILERS` / `DEFAULT_RETAILERS` are duplicated and stale | `sqlite_price_repository.py:33-52`, `csv_price_repository.py` | Fixed by US-026 |
| A11 | The client type `InventoryMeta.warnings` has no counterpart in server output | `frontend/src/lib/types/api.ts` | **Doc-only** (noted in US-009 / US-017) |
