# PRD: Change History (docs overhaul, `/api/products`, ucuzu shop, JSON price data)

## Introduction

`main` changed both behaviour and documentation in three steps, and nothing records **what changed**:

1. **2026-10-17 — docs overhaul and `/api/products`.** 26 completed stories from `tasks/prd-documentation-overhaul.md` (US-018 was deferred), merged from the former `ralph/docs-overhaul` branch, plus the follow-up fix `4a04e27` (`GET /api/products`) and the CI removal `03423c5`.
2. **2026-10-18 — the ucuzu price-comparison shop** (`f15fb2c`): catalog columns in the database, four `/api/catalog/*` routes, shop pages at `/`, dashboard moved to `/analiz`.
3. **2026-10-20 — per-store prices and the JSON price data pipeline** (`f701686`, `0707a5c`, data commits `4703400`, `e86d921`, `bcf4537`, `09a0772`): one offer per store, `is_store_latest`, `scripts/csv_to_json.py`, every retailer's prices from `data/prices_json/`, raw price CSVs deleted, Windows launcher fix.

The owning docs already describe the **current** behaviour: they were checked against the code on 2026-10-20. A developer or AI agent who knew the old code still cannot tell whether a difference they see is intended.

This work adds a change history as **sections inside the existing docs** (no new standalone file). It has two parts:

- one summary section in `docs/README.md`, the docs index, with one subsection per step above;
- short "Changed" notes in each owning doc whose behaviour changed, so a reader of that doc sees the change in context.

**Audience:** developers and AI coding agents working in this repository.

## Goals

- A reader of `docs/README.md` can list every behaviour change since the docs overhaul in under a minute, with a link to the doc section that owns it.
- Every removed flag, environment variable, module, file set or response field is named explicitly, with what replaces it, if anything.
- Every owning doc whose behaviour changed has a dated "Changed" note at the point where the behaviour is described.
- No existing current-behaviour text is rewritten; this work only adds history (the one exception is the contract renumbering in US-002).

## Source of truth for the entries

Every entry must be checked against the commit (`git show <hash>`) before it is written. All hashes are on `main`.

### 2026-10-17 — docs overhaul and `/api/products`

| Commit | Change | Owning doc |
|---|---|---|
| `907efe4` US-020 | CI fixed (pytest, Node 24, nonexistent `verify_redis_store.py` step removed); `frontend/package.json` `engines.node >=22.12`; `frontend/.nvmrc` = 24. `verify_falcon_api.py` runs without a DB | `GETTING-STARTED.md` § Prerequisites |
| `03423c5` (CI removal) | GitHub Actions removed: `.github/workflows/ci.yml` deleted; checks run locally only | `TESTING.md` § No continuous integration |
| `637841c` US-025 | `.gitignore` ignores `*.db.staging*` | `DATABASE.md` § Purpose |
| `82609c3` US-021 | Launcher `--sqlite-db` defaults to `PRICES_DB_PATH`, then `data/prices.db` (previously it always overwrote `PRICES_DB_PATH`) | `CONFIGURATION.md` § Launcher flags |
| `e3401ac` US-023 | Removed `--no-sqlite-readonly` and the never-read exports `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS`, `SQLITE_URI` | `CONFIGURATION.md` |
| `99680ca` US-022 | Runtime CSV fallback removed (`adapters/csv_price_repository.py` deleted, `INFLATION_DATA_ROOT` gone). Missing/empty DB → HTTP 503 `database_unavailable`. `/api/health` adds `data.database`. Warning text changed to `all_history requested; history load is uncapped` | `DATABASE.md`, `FALCON_API_CONTRACT.md` §2.3, §3, §4.1 |
| `ccbe59e` US-026 | `DEFAULT_RETAILERS` defined only in `api/filters.py` (Gurmar, Vakko, HomeGoods); unused `SUPPORTED_RETAILERS` removed | `FALCON_API_CONTRACT.md` §3 |
| `7ef73ed` US-024 | 404/405/500 rendered as envelopes (`not_found`, `method_not_allowed`, `http_error`, `server_error`); `server_error` message fixed to `Internal server error` (exception text no longer sent) | `FALCON_API_CONTRACT.md` §2.3 |
| `2c0c56a` US-027 | Empty/unset `VITE_API_BASE_URL` means same-origin `/api` (previously `http://localhost:8000`); sidebar placeholder "same origin (/api)" | `CONFIGURATION.md` § Frontend, `frontend/README.md` § API URL |
| `f5d0bbd`…`80bd7dc`, `e1588bf` (US-001–013) | Docs restructured: `SEPARATION.md` → `docs/archive/`; `CONVENTIONS.md`/`CONCERNS.md` merged into `ARCHITECTURE.md`; `GETTING-STARTED.md` is the only setup page; `API.md` reduced to a summary | `docs/README.md` |
| `7292db1`, `e12098f`, `9c13189`, `3aa2ee4` (US-014–017) | Docstrings/TSDoc only; no behaviour change | — (one line in the summary) |
| `eea8f71` US-019 | `AGENTS.md` aligned with GETTING-STARTED; known-issues pointer | — (one line in the summary) |
| `4a04e27` fix | New `GET /api/products` (product names per retailer). Product explorer pickers use it instead of full `/api/history` (580 MB → ~4 MB for Markets). Product-mode `/api/history` requests only the selected retailer. `filters._parse_date_param` renamed to `parse_date_param` | `FALCON_API_CONTRACT.md` §4.7 (§4.7a before US-002), `API.md`, `USER_GUIDE.md` |

### 2026-10-18 — ucuzu price-comparison shop

| Commit | Change | Owning doc |
|---|---|---|
| `f15fb2c` | `products` gains `name_key`, `previous_price`, `price_since`, `is_current` (`CURRENT_WINDOW_DAYS` = 45) and `idx_products_name_key`; **a database rebuild is required** | `DATABASE.md` § Catalog columns |
| `f15fb2c` | New routes `GET /api/catalog/groups`, `/search`, `/item`, `/deals` (`adapters/sqlite_catalog_repository.py`, `domain/catalog.py`); a database without the catalog columns gives 503 `database_outdated` on these routes only | `FALCON_API_CONTRACT.md` §2.3 and §4.11–§4.14 (§4.10–§4.13 before US-002), `API.md` |
| `f15fb2c` | Shop pages at `/` (`/ara`, `/urun/[key]`, `/firsatlar`, `/alarmlar`, price alarms in `localStorage` key `price-alarms`); **the dashboard moved from `/` to `/analiz`**; white/blue design tokens and Inter font | `USER_GUIDE.md`, `frontend/README.md` § Routes |
| `f15fb2c` | New `docs/SETUP.md` (new-machine walkthrough) | `docs/README.md` |

### 2026-10-20 — per-store prices and JSON price data

| Commit | Change | Owning doc |
|---|---|---|
| `f701686` | On Windows the launcher stays in the foreground as the parent and kills the server's process tree when it exits (previously `os.execvp` returned and left Granian workers listening on the port); POSIX still uses `execvp` | `GETTING-STARTED.md` § 5. Run the API |
| `0707a5c` | `products.is_store_latest` added; catalog search counts only each store's latest offers. A database built before this commit gives 503 `database_outdated` on `/api/catalog/*`; rebuild | `DATABASE.md` § Catalog columns, `FALCON_API_CONTRACT.md` §4.12 |
| `0707a5c` | `/api/catalog/item` returns **one offer per store** (its cheapest on the store's newest date) with the store's other products in `other_offers`; `summary` and `lowest_ever` ignore `other_offers` (previously one offer per product, so `offer_count` could exceed `store_count`). The product page lists the other offers under each store row | `FALCON_API_CONTRACT.md` §4.13, `USER_GUIDE.md` § Price comparison shop |
| `0707a5c` | New `scripts/csv_to_json.py`: converts and merges scraper CSVs into `data/prices_json/<Group>_<Store>.json` without overwriting existing prices, skipping dropped stores (`DROPPED_RETAILERS`: Xiaomi, Teknoraks). JSON stems split on the first `_` only (`retailer_stem` is the inverse). Month-day file names are dated from `SCRAPE_START` (2026-02-23). Importing from InflationResearchStudy now goes through `csv_to_json.py` (previously CSVs were copied into `data/raw/`) | `SETUP.md` § 4, `DATA_CONTRACT.md`, `DATABASE.md` § JSON fallback |
| `4703400`, `e86d921` | Every retailer's price history committed as one JSON file per retailer | `DATA_CONTRACT.md` § Partitioned JSON input |
| `bcf4537` | Inflation reference files from InflationResearchStudy | `DATA_CONTRACT.md` § Generated inflation input |
| `09a0772` | Raw price CSVs under `data/raw/` deleted (replaced by the JSON files), including the unusable ones and the mirror's `EpeyKatfg/series.csv`; `data/raw/` keeps only reference files. `/api/history` `source_file` values are now `<Group>_<Store>.json#YYYY-MM-DD` (previously `raw/...csv` paths) | `DATA_CONTRACT.md` § Rules for committed data, `FALCON_API_CONTRACT.md` §4.3 |

## User Stories

Stories run in priority order: US-002, US-001, US-006, US-003, US-004, US-007, US-005.

### US-002: API contract version, renumbering and changes section
**Description:** As an API consumer, I want the contract to say what changed between versions so that I can update a client.

**Acceptance Criteria:**
- [ ] `docs/FALCON_API_CONTRACT.md` header: Specification Version `2.4.0`, Last Updated is the date of this change.
- [ ] Endpoint sections are renumbered in order: `/api/products` (§4.7a) becomes §4.7; `/api/products/search`, `/api/product`, `/api/epeykatfg/monthly-inflation` become §4.8–§4.10; `/api/catalog/groups`, `/search`, `/item`, `/deals` become §4.11–§4.14.
- [ ] Every in-file `§` reference (including §6.1's table and the "§4.10–§4.13" range in the catalog intro) and every inbound reference from other docs uses the new numbers and anchors. Find them with `grep -rnE "§ ?4\.|#4[0-9]+a?-get" docs frontend/README.md AGENTS.md` (skip `docs/archive/`); today that includes `docs/DATABASE.md` § Catalog columns (`§4.10–§4.13`, `#410-get-apicataloggroups`).
- [ ] A new `## 9. Changes` section lists per version, newest first, the client-visible changes, each linking to its section:
  - **2.4.0** (2026-10-20, `0707a5c`, `09a0772`): `/api/catalog/item` returns one offer per store with `other_offers`; catalog search counts only `is_store_latest` offers; `database_outdated` also covers databases without `is_store_latest`; `/api/history` `source_file` values are JSON partition names.
  - **2.3.0** (2026-10-18, `f15fb2c`): the four `/api/catalog/*` routes; 503 `database_outdated`.
  - **2.2.0** (`4a04e27`): new `/api/products`.
  - **2.1.0** (docs overhaul): `/api/health` `data.database`; 503 `database_unavailable`; envelopes for 404/405/500; fixed `server_error` message `Internal server error`; warning text `all_history requested; history load is uncapped`; default retailers Gurmar/Vakko/HomeGoods.
- [ ] No endpoint behaviour text changes other than the section numbers.
- [ ] §6.2 is still identical to `frontend/src/lib/types/api.ts` (diff command in Technical Considerations).
- [ ] Typecheck passes (`cd frontend && npm run check`).

### US-001: Change-history summary for the docs overhaul
**Description:** As a developer returning to the repo, I want one list of what the docs overhaul changed so that I know which differences from the old code are intended.

**Acceptance Criteria:**
- [ ] `docs/README.md` gets a `## Change history` section at the end (after `## Archive`), with a one-line intro saying entries are newest first and that `docs/FALCON_API_CONTRACT.md` §9 lists API changes per version.
- [ ] It has a `### 2026-10-17 — docs overhaul and /api/products` subsection with three groups, in this order: **Breaking / behaviour changes**, **Removed**, **Documentation-only**.
- [ ] Every row of the 2026-10-17 "Source of truth" table is covered. Each bullet is one sentence, names the commit hash, and links to the owning doc section (relative markdown link, anchors included; contract links use the US-002 numbers).
- [ ] "Removed" names each removed item exactly: `--no-sqlite-readonly`, `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS`, `SQLITE_URI`, `INFLATION_DATA_ROOT`, `inflation_dashboard/adapters/csv_price_repository.py`, `SUPPORTED_RETAILERS`, `.github/workflows/ci.yml` (GitHub Actions CI; there is no CI any more), `docs/SEPARATION.md` (moved to `docs/archive/`), `docs/CONVENTIONS.md`/`docs/CONCERNS.md` content (moved to `ARCHITECTURE.md`).
- [ ] States that US-018 (Svelte `@component` blocks) was deferred and is not part of this change.
- [ ] Every relative link and anchor in the new section resolves (checked by hand).
- [ ] Typecheck passes.

### US-006: Change-history summary for the shop and the JSON price data
**Description:** As a developer who knew the repository before the shop existed, I want the change history to cover the shop and the new data pipeline so that I know why the database, routes and `data/` look different.

**Acceptance Criteria:**
- [ ] `docs/README.md` § Change history gets two subsections **above** the 2026-10-17 one, newest first: `### 2026-10-20 — per-store prices and JSON price data` and `### 2026-10-18 — ucuzu price-comparison shop`.
- [ ] Each uses the same three groups as US-001 (omit a group that would be empty).
- [ ] Every row of the 2026-10-18 and 2026-10-20 "Source of truth" tables is covered, one sentence per bullet, with the commit hash and a link to the owning doc section.
- [ ] **Breaking / behaviour changes** says plainly that a database built before `f15fb2c` or before `0707a5c` must be rebuilt (`uv run python scripts/build_database.py`), and that the dashboard moved from `/` to `/analiz`.
- [ ] **Removed** names: the raw price CSVs under `data/raw/` (`09a0772`; prices now come from `data/prices_json/`), copying upstream CSVs into `data/raw/` as the import method (replaced by `scripts/csv_to_json.py`), and the dropped stores `Communication / Xiaomi`, `Communication / Teknoraks` and the mirror's `Technology.json`.
- [ ] Every relative link and anchor in the new subsections resolves (checked by hand).
- [ ] Typecheck passes.

### US-003: "Changed" notes in configuration and data docs (2026-10-17)
**Description:** As an operator upgrading an existing deployment, I want each changed variable or flag flagged where it is documented so that I don't keep using a removed one.

**Acceptance Criteria:**
- [ ] Notes use the exact form `> **Changed 2026-10-17:** <what changed>; previously <old behaviour>. See [change history](README.md#change-history).` (adjust the relative path per file).
- [ ] `docs/CONFIGURATION.md` § Launcher flags: `--sqlite-db` now defaults to `PRICES_DB_PATH` (previously the launcher overwrote it), and `--no-sqlite-readonly` and the five `SQLITE_*` exports were removed.
- [ ] `docs/CONFIGURATION.md` § API and data variables: `INFLATION_DATA_ROOT` was removed.
- [ ] `docs/CONFIGURATION.md` § Frontend: an empty `VITE_API_BASE_URL` now means same origin (previously `http://localhost:8000`).
- [ ] `docs/DATABASE.md` § Purpose: the runtime CSV fallback was removed and a missing database returns 503 (previously the API fell back to CSV, which found no files in the committed layout).
- [ ] `docs/DATA_CONTRACT.md` § Ownership: `data/raw` is no longer read at runtime.
- [ ] Each note is one or two sentences; no existing current-behaviour text is rewritten.
- [ ] Typecheck passes.

### US-004: "Changed" notes in frontend and user docs (2026-10-17)
**Description:** As a frontend developer, I want the frontend docs to flag the changed defaults and the new product-list request so that I understand why the code differs from older versions.

**Acceptance Criteria:**
- [ ] Notes use the same `> **Changed 2026-10-17:** …` form as US-003 and link to `docs/README.md#change-history`.
- [ ] `frontend/README.md` § API URL: the default changed to same origin (previously `http://localhost:8000`).
- [ ] `frontend/README.md` § Dashboard views (`/analiz`): the Product explorer pickers now use `/api/products` (previously the full `/api/history`, which failed for large categories with "API response from /api/history was not valid JSON").
- [ ] `docs/USER_GUIDE.md` § 1. Product price explorer: add only the "Changed" note; do not change the behaviour text.
- [ ] Typecheck passes.
- [ ] Verify in browser using dev-browser skill: the Product explorer pickers on `/analiz` load for the default Markets category with no "not valid JSON" error. If the skill is unavailable, record this as unverified in the story notes.

### US-007: "Changed" notes for the shop and the JSON price data (2026-10-18, 2026-10-20)
**Description:** As an operator or developer upgrading from before the shop, I want the owning docs to flag the rebuild, the moved dashboard and the new data import so that I don't follow old habits.

**Acceptance Criteria:**
- [ ] Notes use the form of US-003 with the commit's date (`> **Changed 2026-10-18:** …` or `> **Changed 2026-10-20:** …`) and link to `docs/README.md#change-history`.
- [ ] `docs/DATABASE.md` § Catalog columns: the catalog columns were added on 2026-10-18 and `is_store_latest` on 2026-10-20; a database built before either returns 503 `database_outdated` on `/api/catalog/*` until it is rebuilt.
- [ ] `docs/DATA_CONTRACT.md` § Rules for committed data: since 2026-10-20 prices are committed only as JSON (previously as scraper CSVs under `data/raw/`).
- [ ] `docs/SETUP.md` § 4: new scrapes are imported with `scripts/csv_to_json.py` (previously copied into `data/raw/` as CSVs).
- [ ] `docs/GETTING-STARTED.md` § 5. Run the API: the Windows launcher now stays in the foreground and stops the server's workers when it exits (previously workers could keep listening on the port).
- [ ] `docs/USER_GUIDE.md` (intro) and `frontend/README.md` § Routes: the dashboard moved from `/` to `/analiz` on 2026-10-18 (previously it was the site root).
- [ ] `docs/USER_GUIDE.md` § Price comparison shop: the product page shows one offer per store with the store's other listings folded under it (previously one row per product).
- [ ] Each note is one or two sentences; no existing current-behaviour text is rewritten.
- [ ] Typecheck passes.

### US-005: Developer-facing pointers
**Description:** As an AI agent starting in this repo, I want AGENTS.md and DEVELOPMENT.md to point at the change history so that I check it before assuming old behaviour.

**Acceptance Criteria:**
- [ ] `AGENTS.md`: one line next to the existing known-issues pointer: "Recent behaviour changes are listed in [docs/README.md#change-history](docs/README.md#change-history)."
- [ ] `docs/DEVELOPMENT.md`: a checklist item in **API endpoint change**: "Add an entry to the change history in `docs/README.md` and to §9 of `FALCON_API_CONTRACT.md` (bump its version)."
- [ ] `docs/DEVELOPMENT.md`: a checklist item in **Schema or data layout change**, **Data update** (only when the layout or import method changes) and **Configuration change**: "Add an entry to the change history in `docs/README.md`."
- [ ] Typecheck passes.

## Functional Requirements

- FR-1: The change history must be added inside existing files only (`docs/README.md`, `FALCON_API_CONTRACT.md`, `CONFIGURATION.md`, `DATABASE.md`, `DATA_CONTRACT.md`, `SETUP.md`, `GETTING-STARTED.md`, `frontend/README.md`, `USER_GUIDE.md`, `AGENTS.md`, `DEVELOPMENT.md`). No new `CHANGELOG.md`.
- FR-2: Every entry must cite the commit hash it describes and be checked against `git show <hash>`.
- FR-3: "Changed" notes use the exact form `> **Changed <YYYY-MM-DD>:** <what changed>; previously <old behaviour>. See [change history](…).`, with the date of the change (2026-10-17, 2026-10-18 or 2026-10-20).
- FR-4: Current-behaviour text must not be rewritten; this work only adds history notes. The one exception is the contract renumbering in US-002.
- FR-5: Relative links and anchors are checked by hand. Do not add automated doc tests.
- FR-6: One commit per story: `docs: US-0XX - <title>`.

## Non-Goals

- No new behaviour or code changes (the contract renumbering in US-002 is a docs-only change).
- No standalone `CHANGELOG.md` and no release tooling (semantic-release, towncrier, etc.).
- No history for commits before `907efe4`.
- No entries for data-only refreshes that change no layout or format.
- No documentation of US-018; it was deferred.
- No rewrite of `docs/archive/`, `docs/research/` or the dated `FALCON-*` reports.

## Technical Considerations

- GitHub anchors: `## Change history` → `#change-history`; headings containing `:`, backticks, `/` or `.` drop those characters (for example `#large-files-scriptsdata_filespy`, `### 4.11 \`GET /api/catalog/groups\`` → `#411-get-apicataloggroups`).
- The contract's §6.2 is a verbatim copy of `frontend/src/lib/types/api.ts`. Renumbering must not touch it; re-check with `diff <(sed -n '/^```typescript$/,/^```$/p' docs/FALCON_API_CONTRACT.md | sed '1d;$d') frontend/src/lib/types/api.ts`.
- `docs/CONFIGURATION.md` and `docs/ARCHITECTURE.md` cite `file:line`. These stories change no code, so those references stay valid.
- Windows: scripted edits must write LF (`newline="\n"`); `.gitattributes` normalizes on commit anyway.

## Success Metrics

- Every row of the three "Source of truth" tables appears exactly once in `docs/README.md#change-history`.
- `grep -rn "Changed 2026-10-1[78]\|Changed 2026-10-20" docs frontend/README.md AGENTS.md` returns a note in each doc listed in US-003, US-004 and US-007.
- A reviewer comparing `git log 907efe4^..main` with the change history finds no behaviour change that is missing from it.

## Open Questions

- Should US-018 get its own placeholder entry ("pending") so it isn't forgotten, or stay only in `scripts/ralph/prd.json`?
- Should the contract's §9 keep the old 2.0.0 → 2.1.0 changes, or start the list at 2.1.0 (as written above)?
