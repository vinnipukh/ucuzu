# Inflation Study Dashboard — Svelte Frontend

Svelte 5 / SvelteKit production client for the standalone Inflation Study Dashboard. It is a static, client-side SPA that queries the Falcon REST API over HTTP; it does not scan CSV/JSON files and has no server-side rendering.

- **Framework:** Svelte 5 runes + SvelteKit (`adapter-static`, `ssr = false`)
- **Charts:** Apache ECharts
- **API contract:** `../docs/FALCON_API_CONTRACT.md`
- **Design system:** Minimal Swiss-style tokens in `src/app.css`

## Quick start

From the web repository root:

```bash
uv run python scripts/run_falcon_server.py --engine granian --port 8000
```

Then:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000`.

## Production build

```bash
npm run build
npm run preview
```

The static output is written to `frontend/build/`.

## API URL

- Build-time default: `VITE_API_BASE_URL` in `frontend/.env.example`.
- Empty value: use same-origin `/api` requests through the Vite/server proxy.
- Runtime override: edit the API URL in the sidebar and apply it.

## Views

1. **Product Explorer** — latest/cheapest metrics, full-history monthly average, optional daily chart and raw history.
2. **Retailer Averages** — average/median trends across selected retailers.
3. **Price Movers** — largest drops from peak and gains since first observation.
4. **Coverage Overview** — products, observations, categories and skipped-file diagnostics.
5. **EpeyKatfg Monthly** — generated month-over-month Carli, Dutot and TÜİK-weighted inflation series.

## State and filters

- `src/lib/stores/filters.svelte.ts` owns API URL, retailer, date and file-bound state.
- Gurmar is selected by default when present in inventory.
- Date range defaults to the latest 60 days.
- The file cap defaults to 45 per retailer; all-history mode sends `max_files=0`.
- Search normalizes Turkish characters and ranks prefix, substring and fuzzy matches.

## Source layout

```text
src/
  app.css
  lib/
    api/client.ts
    types/api.ts
    stores/filters.svelte.ts
    components/
    utils/
    views/
  routes/
    +layout.ts
    +page.svelte
```

## Checks

```bash
npm run check
npm run build
```

Keep API changes synchronized with both `src/lib/types/api.ts` and `../docs/FALCON_API_CONTRACT.md`.
