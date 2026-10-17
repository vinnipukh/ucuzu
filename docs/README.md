# Documentation Index

Each topic has one owning document; other files link to it instead of repeating it.

## Start here

- [Project README](../README.md) — pitch, quickstart and links.
- [Getting Started](GETTING-STARTED.md) — the only place for install, build-database, run and verify commands.
- [Architecture](ARCHITECTURE.md) — source layout, layer boundaries, request flow and known issues.
- [Agent rules](../AGENTS.md) — hard rules for coding agents: repository boundary, data rules, change policy.

## API and frontend

- [Falcon API Contract](FALCON_API_CONTRACT.md) — authoritative API reference.
- [API Summary](API.md) — endpoint table, link to the contract and performance notes.
- [User Guide](USER_GUIDE.md) — end-user walkthrough of the SPA.
- [Frontend README](../frontend/README.md) — frontend-only state, environment and source layout.

## Data and configuration

- [Data Contract](DATA_CONTRACT.md) — `data/` layout and file formats.
- [Database](DATABASE.md) — schema, indexes, build pipeline and runtime connection mode.
- [Configuration](CONFIGURATION.md) — every environment variable and launcher flag.

## Contributing

- [Development](DEVELOPMENT.md) — change checklists (API change, schema/data layout change, data update, frontend change).
- [Testing](TESTING.md) — test suite, verification scripts and manual QA.
- [Conventions](CONVENTIONS.md) — pointer; merged into [Architecture](ARCHITECTURE.md#conventions).
- [Concerns](CONCERNS.md) — pointer; merged into [Architecture](ARCHITECTURE.md#operational-notes).

## Research and reports

Dated material: findings reflect the code at the time they were written.

- [Falcon API Optimization Report (2026-09-03)](FALCON-API-OPTIMIZATION-REPORT-2026-09-03.md) — synthesis of the four research notes.
- [Falcon Deployment & Server Tuning Research](FALCON-DEPLOYMENT-TUNING-RESEARCH.md) — WSGI server choice and tuning.
- [research/research-notes-falcon-framework-optimization.md](research/research-notes-falcon-framework-optimization.md) — Falcon request path, middleware, routing and media handling.
- [research/research-notes-profiling-db-caching-falcon.md](research/research-notes-profiling-db-caching-falcon.md) — profiling, SQLite and response caching.
- [research/falcon-benchmarks-case-studies.md](research/falcon-benchmarks-case-studies.md) — published Falcon benchmarks and production case studies.
- [benchmarks/](benchmarks/) — raw load-test results (Granian vs Gunicorn, health and mixed workloads).
- [db_benchmark_results.json](db_benchmark_results.json) — raw SQLite connection-strategy benchmark results.

## Archive

Historical material; not current setup guidance.

- [archive/SEPARATION.md](archive/SEPARATION.md) — the 2026 extraction of this repository from the monorepo.
- [archive/monorepo/](archive/monorepo/README.md) — original monorepo documentation.
- [archive/planning/](archive/planning/README.md) — Streamlit-era planning, phases and roadmap.
- [archive/static-inflation-report.html](archive/static-inflation-report.html) — early static inflation report page.
