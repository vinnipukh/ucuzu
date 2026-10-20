# ucuzu — price comparison and Inflation Study Dashboard

Price tracking for Turkish retailers, in two parts that share one Falcon (WSGI) API and one read-only SQLite database of daily scraped prices:

- **ucuzu** (`/`): a minimalist cimri-style price-comparison shop. Search across stores, compare one product's prices store by store, see price histories and recent price drops, and set price alarms.
- **Inflation Study Dashboard** (`/analiz`): research views over the same prices, plus EpeyKatfg monthly inflation series.

The frontend is a Svelte 5 / SvelteKit single-page app. The data covers about 200 retailers across food, cosmetics, home goods, clothing, building supplies, electronics, housing rent and more.

Repository: [github.com/vinnipukh/ucuzu](https://github.com/vinnipukh/ucuzu) (previously `cimri-clone`, and before that `inflationstudymirror-web`).

Scrapers, inflation calculators and TÜİK methodology live in the separate data repository [`vinnipukh/inflationstudymirror`](https://github.com/vinnipukh/inflationstudymirror) (mirror of the upstream [`urazkagangunes/InflationResearchStudy`](https://github.com/urazkagangunes/InflationResearchStudy)). Their output is committed here under `data/`.

```text
data/ (committed per-retailer price JSON) → scripts/build_database.py → data/prices.db → Falcon API → Svelte SPA (shop + dashboard)
```

## Quickstart

Needs Python ≥ 3.14, [uv](https://docs.astral.sh/uv/) and Node.js 24 (≥ 22.12).

```bash
uv sync --extra dev
uv run python scripts/build_database.py
uv run python scripts/run_falcon_server.py --engine granian --port 8000
cd frontend && npm install && npm run dev
```

Run the last command in a second terminal, then open `http://localhost:5173` (shop) or `http://localhost:5173/analiz` (dashboard). The full guide, including tests and production deployment, is [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md). For a new machine, including converting new scrapes from the upstream data repository into JSON, follow [docs/SETUP.md](docs/SETUP.md).

## ucuzu shop

- **Search** (`/ara`) — every word must appear in the product name; filter by category and store, sort by relevance, price or largest drop.
- **Product page** (`/urun/<name>`) — products with the same normalized name are compared across stores: cheapest current price, one offer per store (its other listings folded under it), price history per store, lowest price seen.
- **Deals** (`/firsatlar`) — current offers whose latest price change was a drop.
- **Price alarms** (`/alarmlar`) — a target price per product, stored in your browser.

Products are matched across stores by name only (the data has no shared product id), so differently worded listings stay separate.

## Dashboard views (`/analiz`)

1. **Product explorer** — one product's price history and summary.
2. **Retailer averages** — average or median price trends per retailer.
3. **Price movers** — biggest drops from peak and gains since first seen.
4. **Coverage overview** — observations over time and per category.
5. **EpeyKatfg monthly** — month-over-month inflation series.

See the [User Guide](docs/USER_GUIDE.md).

## Documentation

- [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) — install, build the database, run and verify.
- [docs/SETUP.md](docs/SETUP.md) — new-machine walkthrough: building the database, importing new scrapes from InflationResearchStudy.
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — using the shop and the dashboard.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — source layout, layer boundaries, request flow, known issues.
- [docs/FALCON_API_CONTRACT.md](docs/FALCON_API_CONTRACT.md) — authoritative HTTP API reference.
- [docs/README.md](docs/README.md) — index of all documentation.
- [AGENTS.md](AGENTS.md) — rules for coding agents.

Databases (`*.db`) and `.env` files are never committed.
