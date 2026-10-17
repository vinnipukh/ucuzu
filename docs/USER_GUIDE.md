# User Guide

## Start the application

Start the Falcon API on port 8000 and the Svelte frontend on port 5173. Open `http://localhost:5173`.

The API base URL is configurable in the sidebar. The default is `http://localhost:8000`.

## Sidebar

- **API base URL** — change the Falcon server and reload inventory.
- **Retailers** — search and select one or more data sources. Every retailer in the inventory is selected by default; remove some to speed up views.
- **Date range** — restrict time-series queries; defaults to the last 60 days of data.
- **Max files per retailer** — bound history loading (45) when **Load all files** is off.
- **Load all files** — on by default: every file in the date range is used, without the per-retailer cap.
- **Inventory summary** — file count and available date range.

## Views

### Product Explorer

Select a retailer and product to view latest/cheapest metrics, the full-history monthly average chart, optional daily history and the raw observation table.

### Retailer Averages

Compare average or median price trends across selected retailers.

### Price Movers

Show the largest drops from peak and gains since first observation, with retailer scope and row limits.

### Coverage Overview

Show retailer/product/observation totals, tracked products over time, category distribution and skipped-file diagnostics.

### EpeyKatfg Monthly

Show month-over-month Carli average, Dutot basket index, TÜİK-weighted change, metric cards and the detailed monthly table. The view is empty when the configured inflation artifact is unavailable.

## Tips

- Monthly Product Explorer charts use the product's complete available history; daily history follows the sidebar date range.
- Search tolerates Turkish characters, prefixes, substrings and close matches.
- The first request for a new filter combination can be slower while the API reads a cold data window.
- Use a smaller date range or file cap if a request is too broad.

## Troubleshooting

- **API unreachable:** confirm the API is running and the sidebar URL is correct.
- **No inventory:** the web deployment may not have a built/configured database.
- **Monthly EpeyKatfg view empty:** configure `EPEYKATFG_MONTHLY_CSV` on the API deployment.
- **Slow first load:** reduce the date/file bounds and retry after caches warm.
