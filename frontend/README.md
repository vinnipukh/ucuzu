# ucuzu and Inflation Study Dashboard — Svelte Frontend

Svelte 5 / SvelteKit client for the Inflation Study Dashboard. It is a static, client-side SPA that queries the Falcon REST API over HTTP; it does not read data files and has no server-side rendering. It contains a Turkish price-comparison shop (wordmark "ucuzu") at `/` and the inflation dashboard at `/analiz`.

- **Framework:** Svelte 5 runes + SvelteKit (`adapter-static` with an `index.html` fallback, `ssr = false`)
- **Charts:** Apache ECharts
- **API contract:** [`../docs/FALCON_API_CONTRACT.md`](../docs/FALCON_API_CONTRACT.md)
- **Design tokens:** `src/app.css` (white/blue theme, Inter font; chart palette in `src/lib/utils/chartTheme.svelte.ts`)
- **Node.js:** 24 LTS recommended (`.nvmrc`), ≥ 22.12 required (`engines`)

## Setup

Install, run and build commands are in [docs/GETTING-STARTED.md](../docs/GETTING-STARTED.md). `npm run build` writes the static site to `frontend/build/`.

## API URL

- `VITE_API_BASE_URL` (see [`.env.example`](.env.example)) is read at build time. **Empty or unset (the default) means same origin:** the SPA requests relative `/api/...` URLs.
- In `npm run dev`, Vite proxies `/api` to `http://localhost:8000` (`vite.config.ts`). `npm run preview` and static hosting have no proxy: serve the build behind a reverse proxy that routes `/api`, or build with `VITE_API_BASE_URL` set to the API's origin. Both setups are described in [GETTING-STARTED.md](../docs/GETTING-STARTED.md#how-the-dashboard-reaches-the-api).
- Runtime override: the sidebar's API settings change `filters.apiBaseUrl` for the session (empty = same origin).

> **Changed 2026-10-17:** the default API URL is the same origin; previously an empty `VITE_API_BASE_URL` meant `http://localhost:8000`. See [change history](../docs/README.md#change-history).

## Routes

| URL | File | Purpose | API |
|---|---|---|---|
| `/` | `routes/(shop)/+page.svelte` | Shop home: deal rail, popular items of the four largest groups, popular stores | `/api/catalog/deals`, `/api/catalog/search`, `/api/catalog/groups` |
| `/ara` | `routes/(shop)/ara/+page.svelte` | Search with group/store filters, sort and paging; URL params `q`, `group`, `store`, `sort`, `sayfa` (page, 24 items each) | `/api/catalog/search` |
| `/urun/[key]` | `routes/(shop)/urun/[key]/+page.svelte` | Item comparison: one offer per store, cheapest first (the store's `other_offers` expandable under it), stale offers collapsed, pack options with the price per package, per-store price-history chart (1 month / 3 months / all), other sizes (the item's family), similar items, price alarm form | `/api/catalog/item`, `/api/catalog/search` |
| `/firsatlar` | `routes/(shop)/firsatlar/+page.svelte` | Deals: filter by group, minimum drop and period | `/api/catalog/deals` |
| `/alarmlar` | `routes/(shop)/alarmlar/+page.svelte` | Price alarms with each item's current lowest price | `/api/catalog/item` |
| `/analiz` | `routes/analiz/+page.svelte` | Inflation dashboard (the five views below) | see below |

`(shop)` is a SvelteKit layout group: it adds `SiteHeader` and the shop footer without a URL segment. `[key]` is `<slug>,<id>`: a slug of the item's name and its permanent item ID (`itemHref` / `itemIdFromParam` in `src/lib/catalog.ts`); only the ID is read, cimri-style (`/urun/pinar-sut-1-l,123`).

> **Changed 2026-10-18:** the dashboard moved from `/` to `/analiz` and the shop took over `/`; previously the dashboard was the site root. See [change history](../docs/README.md#change-history).

## Dashboard views (`/analiz`)

1. **Product explorer** — retailer/product pickers (`/api/products`), latest/cheapest metrics, full-history monthly average chart (`/api/product`), optional daily chart and raw history (`/api/history`).
2. **Retailer averages** — average/median trends across loaded retailers.
3. **Price movers** — largest drops from peak and gains since first observation.
4. **Coverage overview** — products, observations, categories over time.
5. **EpeyKatfg monthly** — month-over-month Carli, Dutot and TÜİK-weighted inflation series.

> **Changed 2026-10-17:** the Product explorer's retailer and product pickers load from `/api/products`; previously they loaded the full `/api/history`, which failed for large categories with "API response from /api/history was not valid JSON". See [change history](../docs/README.md#change-history).

User-facing behaviour is described in [docs/USER_GUIDE.md](../docs/USER_GUIDE.md).

## State and defaults

`src/lib/stores/filters.svelte.ts` owns the API URL, category, retailer, date and file-cap state.

- **Category:** retailers load one category at a time. The initial category is the one remembered in `localStorage` (`inflation-dashboard:category`), else `DEFAULT_CATEGORY` (`'Markets'`), else the first category. Editing the retailer list by hand clears the category label unless it still matches exactly.
- **Dates:** the last 60 days of the inventory range (not before its first date).
- **Files:** `DEFAULT_ALL_HISTORY = true`, so requests send `all_history=true` and `max_files=0`. With all-history off, the file cap (`maxFiles`) defaults to 45 and the slider ranges 10–160.
- **Theme:** `src/lib/themes.svelte.ts` stores `auto | light | dark` in `localStorage` (`inflation-dashboard-theme`); `auto` follows `prefers-color-scheme`.
- **Search:** `src/lib/utils/search.ts` normalizes Turkish characters and ranks prefix, substring and fuzzy matches.
- **Catalog groups:** `src/lib/stores/catalog.svelte.ts` loads `/api/catalog/groups` once per page load and shares it between the shop header, footer and pages.
- **Price alarms:** `src/lib/stores/alarms.svelte.ts` keeps `{id, name, target, priceWhenSet, createdAt}` entries (`id`: the item ID) in `localStorage` (`price-alarms`); entries without a numeric `id`, saved before item IDs, are dropped on load. Nothing is sent to the API, which stays read-only.

## Source layout

```text
src/
  app.css, app.html, app.d.ts
  lib/
    index.ts                 $lib entry (empty)
    themes.svelte.ts         Auto/Light/Dark theme state
    api/client.ts            fetchApi(): the only HTTP client
    types/api.ts             TypeScript mirror of the API contract
    catalog.ts               shop helpers: Turkish group labels, item/search links, TL and date formatting
    stores/filters.svelte.ts global filter state (dashboard)
    stores/catalog.svelte.ts catalog groups (shop)
    stores/alarms.svelte.ts  price alarms in localStorage (shop)
    components/              Header, Sidebar, Chart, DataTable, selects, alerts, spinner;
                             shop: SiteHeader, ProductCard, Icon
    utils/                   chart options/theme, formatting, search, AsyncResource
    views/                   the five dashboard views
  routes/
    +layout.ts               ssr = false
    +layout.svelte           imports app.css, applies the theme, sets the favicon
    (shop)/                  shop layout and pages: /, /ara, /urun/[key], /firsatlar, /alarmlar
    analiz/+page.svelte      dashboard shell at /analiz: inventory, sidebar, tabs
```

## Checks

`npm run check` must pass with no errors or warnings (see [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md)). Keep API changes synchronized with both `src/lib/types/api.ts` and `../docs/FALCON_API_CONTRACT.md`.
