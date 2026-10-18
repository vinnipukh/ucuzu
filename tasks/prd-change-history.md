# PRD: Change History for the Docs Overhaul and `/api/products`

## Introduction

Branch `ralph/docs-overhaul` changed both behaviour and documentation. There are 26 completed stories from `tasks/prd-documentation-overhaul.md` (US-018 was deferred) and one follow-up fix (`4a04e27`, `GET /api/products`). The owning docs already describe the **new** behaviour. Nothing records **what changed**, so a developer or AI agent who knew the old code cannot tell whether a difference they see is intended.

This work adds a change history as **sections inside the existing docs** (no new standalone file). It has two parts:

- one summary section in `docs/README.md`, the docs index;
- short "Changed" notes in each owning doc whose behaviour changed, so a reader of that doc sees the change in context.

**Audience:** developers and AI coding agents working in this repository.

## Goals

- A reader of `docs/README.md` can list every behaviour change on the branch in under a minute, with a link to the doc section that owns it.
- Every removed flag, environment variable, module or response field is named explicitly, with what replaces it, if anything.
- Every owning doc whose behaviour changed has a dated "Changed" note at the point where the behaviour is described.
- No existing current-behaviour text is rewritten; this work only adds history.

## Source of truth for the entries

Every entry must be checked against the commit (`git show <hash>`) before it is written. Hashes are on `ralph/docs-overhaul`:

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
| `4a04e27` fix | New `GET /api/products` (product names per retailer). Product explorer pickers use it instead of full `/api/history` (580 MB → ~4 MB for Markets). Product-mode `/api/history` requests only the selected retailer. `filters._parse_date_param` renamed to `parse_date_param` | `FALCON_API_CONTRACT.md` §4.7a, `API.md`, `USER_GUIDE.md` |

## User Stories

### US-001: Change-history summary in the docs index
**Description:** As a developer returning to the repo, I want one list of what changed on this branch so that I know which differences from the old code are intended.

**Acceptance Criteria:**
- [ ] `docs/README.md` gets a `## Change history` section at the end, with a `### 2026-10-17 — docs overhaul and /api/products` subsection.
- [ ] The subsection has three groups, in this order: **Breaking / behaviour changes**, **Removed**, **Documentation-only**.
- [ ] Every row of the "Source of truth" table above is covered. Each bullet is one sentence, names the commit hash, and links to the owning doc section (relative markdown link, anchors included).
- [ ] "Removed" names each removed item exactly: `--no-sqlite-readonly`, `SQLITE_DB_PATH`, `SQLITE_READ_ONLY`, `SQLITE_JOURNAL_MODE`, `SQLITE_SYNCHRONOUS`, `SQLITE_URI`, `INFLATION_DATA_ROOT`, `inflation_dashboard/adapters/csv_price_repository.py`, `SUPPORTED_RETAILERS`, `.github/workflows/ci.yml` (GitHub Actions CI), `docs/SEPARATION.md` (moved), `docs/CONVENTIONS.md`/`docs/CONCERNS.md` content (moved).
- [ ] States that US-018 (Svelte `@component` blocks) was deferred and is not part of this change.
- [ ] Every relative link in the new section resolves (checked by hand).
- [ ] Typecheck passes (`cd frontend && npm run check`).

### US-002: API contract version and changes subsection
**Description:** As an API consumer, I want the contract to say what changed between versions so that I can update a client.

**Acceptance Criteria:**
- [ ] `docs/FALCON_API_CONTRACT.md` header: Specification Version `2.2.0` (2.1.0 was the US-008 rewrite; 2.2.0 adds `/api/products`), Last Updated is the date of this change.
- [ ] A new `## 9. Changes` section lists, per version (2.2.0, then 2.1.0), the client-visible changes: new `/api/products`; `/api/health` `data.database`; 503 `database_unavailable`; envelopes for 404/405/500; fixed `server_error` message; new warning text; default retailers. Each item links to its section (§2.3, §3, §4.1, §4.7a).
- [ ] Section §4.7a is renumbered so endpoint sections are in order (e.g. `/api/products` becomes §4.7 and search/detail/monthly shift by one). Every in-file `§` reference and every inbound link from other docs (`grep -rn "4\.7\|4\.8\|4\.9" docs`) is updated.
- [ ] No endpoint behaviour text is changed.
- [ ] Typecheck passes.

### US-003: "Changed" notes in configuration and data docs
**Description:** As an operator upgrading an existing deployment, I want each changed variable or flag flagged where it is documented so that I don't keep using a removed one.

**Acceptance Criteria:**
- [ ] `docs/CONFIGURATION.md`: a `> **Changed 2026-10-17:** …` note under § Launcher flags (`--sqlite-db` now respects `PRICES_DB_PATH`; `--no-sqlite-readonly` and the five `SQLITE_*` exports removed) and under § Frontend (empty `VITE_API_BASE_URL` now means same origin, previously `http://localhost:8000`). Also a note under § API and data variables that `INFLATION_DATA_ROOT` was removed.
- [ ] `docs/DATABASE.md` § Purpose: a note that the runtime CSV fallback was removed and a missing DB now returns 503 (previously it fell back to CSV, which found no files in the committed layout).
- [ ] `docs/DATA_CONTRACT.md` § Ownership: a note that `data/raw` is no longer read at runtime.
- [ ] Each note is one to two sentences and links to the `docs/README.md` change-history section.
- [ ] Typecheck passes.

### US-004: "Changed" notes in frontend and user docs
**Description:** As a frontend developer, I want the frontend docs to flag the changed defaults and the new product-list request so that I understand why the code differs from older branches.

**Acceptance Criteria:**
- [ ] `frontend/README.md` § API URL: note that the default changed to same-origin.
- [ ] `frontend/README.md` § Views: note that the Product explorer's pickers now use `/api/products` (previously the full `/api/history`, which broke for large categories with "API response from /api/history was not valid JSON").
- [ ] `docs/USER_GUIDE.md` § 1. Product price explorer: one sentence that the pickers list products seen in the date window (already true; add only the "Changed" note, not new behaviour text).
- [ ] Each note links to the `docs/README.md` change-history section.
- [ ] Typecheck passes.
- [ ] Verify in browser using dev-browser skill: the Product explorer pickers load for the default Markets category (no "not valid JSON" error). If the skill is unavailable, record this as unverified in the story notes.

### US-005: Developer-facing pointers
**Description:** As an AI agent starting in this repo, I want AGENTS.md and DEVELOPMENT.md to point at the change history so that I check it before assuming old behaviour.

**Acceptance Criteria:**
- [ ] `AGENTS.md`: one line next to the existing known-issues pointer: "Recent behaviour changes are listed in docs/README.md#change-history."
- [ ] `docs/DEVELOPMENT.md`: a checklist item in **API endpoint change** and **Configuration change**: "Add an entry to the change history in `docs/README.md` (and §9 of the contract for API changes)."
- [ ] Typecheck passes.

## Functional Requirements

- FR-1: The change history must be added inside existing files only (`docs/README.md`, `FALCON_API_CONTRACT.md`, `CONFIGURATION.md`, `DATABASE.md`, `DATA_CONTRACT.md`, `frontend/README.md`, `USER_GUIDE.md`, `AGENTS.md`, `DEVELOPMENT.md`). No new `CHANGELOG.md`.
- FR-2: Every entry must cite the commit hash it describes and be checked against `git show <hash>`.
- FR-3: "Changed" notes use the exact form `> **Changed 2026-10-17:** <what changed>; previously <old behaviour>. See [change history](…).`
- FR-4: Current-behaviour text written by the docs overhaul must not be rewritten; this work only adds history notes. The one exception is the contract renumbering in US-002.
- FR-5: Relative links and anchors are checked by hand. Do not add automated doc tests (same rule as the overhaul PRD).
- FR-6: One commit per story: `docs: US-0XX - <title>`.

## Non-Goals

- No new behaviour or code changes (the contract renumbering in US-002 is a docs-only change).
- No standalone `CHANGELOG.md` and no release tooling (semantic-release, towncrier, etc.).
- No history for commits before `907efe4` (before this branch).
- No documentation of US-018; it was deferred.
- No rewrite of `docs/archive/`, `docs/research/` or the dated `FALCON-*` reports.

## Technical Considerations

- GitHub anchors: `## Change history` → `#change-history`; headings containing `:`, backticks, `/` or `.` drop those characters (for example `#large-files-scriptsdata_filespy`).
- The contract's §6.2 is a verbatim copy of `frontend/src/lib/types/api.ts`. Renumbering must not touch it; re-check with `diff <(sed -n '/^```typescript$/,/^```$/p' docs/FALCON_API_CONTRACT.md | sed '1d;$d') frontend/src/lib/types/api.ts`.
- `docs/CONFIGURATION.md` and `docs/ARCHITECTURE.md` cite `file:line`. These stories change no code, so those references stay valid.
- Windows: scripted edits must write LF (`newline="\n"`); `.gitattributes` normalizes on commit anyway.

## Success Metrics

- Every row of the "Source of truth" table appears exactly once in `docs/README.md#change-history`.
- `grep -rn "Changed 2026-10-17" docs frontend/README.md AGENTS.md` returns a note in each doc listed in US-003 and US-004.
- A reviewer comparing `git log main..ralph/docs-overhaul` with the change history finds no behaviour change that is missing from it.

## Open Questions

- Should the change-history date be the branch merge date instead of 2026-10-17? If the merge happens later, update the dates in one pass.
- Should US-018 get its own placeholder entry ("pending") so it isn't forgotten, or stay only in `scripts/ralph/prd.json`?
- Should the contract keep the old 2.0.0 → 2.1.0 changes in §9, or start the list at 2.1.0?
