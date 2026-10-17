# Inflation Study Dashboard

A price-tracking dashboard for Turkish retailers: a Svelte 5 / SvelteKit single-page app on top of a Falcon (WSGI) API that serves daily scraped prices from a read-only SQLite database. It covers about 200 retailers across food, clothing, housing rent, health, communication and more, plus EpeyKatfg monthly inflation series.

Repository: [github.com/vinnipukh/cimri-clone](https://github.com/vinnipukh/cimri-clone) (the project was previously referred to as `inflationstudymirror-web`).

Scrapers, inflation calculators and TÜİK methodology live in the separate data repository [`vinnipukh/inflationstudymirror`](https://github.com/vinnipukh/inflationstudymirror) (mirror of the upstream [`urazkagangunes/InflationResearchStudy`](https://github.com/urazkagangunes/InflationResearchStudy)). Their output is committed here under `data/`.

```text
data/ (committed CSV + JSON) → scripts/build_database.py → data/prices.db → Falcon API → Svelte SPA
```

## Quickstart

Needs Python ≥ 3.14, [uv](https://docs.astral.sh/uv/) and Node.js 24 (≥ 22.12).

```bash
uv sync --extra dev
uv run python scripts/build_database.py
uv run python scripts/run_falcon_server.py --engine granian --port 8000
cd frontend && npm install && npm run dev
```

Run the last command in a second terminal, then open `http://localhost:5173`. The full guide, including tests and production deployment, is [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md).

## Dashboard views

1. **Product explorer** — one product's price history and summary.
2. **Retailer averages** — average or median price trends per retailer.
3. **Price movers** — biggest drops from peak and gains since first seen.
4. **Coverage overview** — observations over time and per category.
5. **EpeyKatfg monthly** — month-over-month inflation series.

See the [User Guide](docs/USER_GUIDE.md).

## Documentation

- [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) — install, build the database, run and verify.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — source layout, layer boundaries, request flow, known issues.
- [docs/FALCON_API_CONTRACT.md](docs/FALCON_API_CONTRACT.md) — authoritative HTTP API reference.
- [docs/README.md](docs/README.md) — index of all documentation.
- [AGENTS.md](AGENTS.md) — rules for coding agents.

Databases (`*.db`) and `.env` files are never committed.
