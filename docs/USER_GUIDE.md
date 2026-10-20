# User Guide

How to use the site. To start it, follow [GETTING-STARTED.md](GETTING-STARTED.md), then open `http://localhost:5173` (or wherever the site is deployed).

The site has two parts:

- the **ucuzu** price-comparison shop at `/` (Turkish), described in [Price comparison shop](#price-comparison-shop);
- the **inflation dashboard** at `/analiz` (linked as **Analiz** in the shop header and "Enflasyon analizi" in its footer), described from [Dashboard header](#dashboard-header) on. Its "← ucuzu" link returns to the shop.

> **Changed 2026-10-18:** the dashboard moved to `/analiz` when the shop took over `/`; previously the dashboard was the site root. See [change history](README.md#change-history).

## Price comparison shop

The same product is matched across stores by its normalized name, so one product page compares every store that sells it. Only current prices are listed: a store's price counts when it was seen within 7 days of that store's newest data and within 45 days of the newest data overall, so stores that are no longer scraped drop out. Rental listings (`HousesRent`) are not part of the shop.

- **Header** — the search box (searches `/ara`), a category menu, links to **Fırsatlar** (deals), **Fiyat Alarmı** (price alarms, with a count) and **Analiz** (the dashboard), and a light/dark toggle.
- **Home (`/`)** — shortcut tiles, recent price drops, popular products of the largest categories and the stores with the most products.
- **Search (`/ara`)** — every word typed must appear in the product name (Turkish letters, case and units such as `1 L`/`1l` are normalized). Filter by category and store, sort by **Önerilen** (relevance), **En düşük fiyat**, **En yüksek fiyat** or **En çok düşen** (largest drop), and page through results (24 per page). The URL keeps the state (`q`, `group`, `store`, `sort`, `sayfa`), so searches can be bookmarked.
- **Product page (`/urun/<name>`)** — the cheapest current price and store, the highest current price, the lowest price ever seen and the price gap between stores; one offer per store (its cheapest listing on its newest date), cheapest first, with its latest price change; a store's other listings of the product open under "<store> için N seçenek daha"; offers that are no longer current are folded under "Güncel olmayan … fiyat"; a step chart of each store's price history (1 month, 3 months or all); and similar products.
- **Deals (`/firsatlar`)** — current offers whose latest price change was a drop, largest first. Filter by category, minimum drop (10–50 %) and period (last 7 or 30 days).
- **Price alarms (`/alarmlar`)** — on a product page, **Fiyat alarmı kur** sets a target price (default 5 % below the cheapest current price). The alarms page shows each alarm with the current cheapest price and marks those at or below the target. Alarms are stored only in this browser (`localStorage` key `price-alarms`): they are not sent to the server, no notification is sent, and clearing site data or using another browser loses them.

> **Changed 2026-10-20:** the product page shows one offer per store, with the store's other listings of the product folded under it; previously every matching product was its own row, so one store could appear several times. See [change history](README.md#change-history).

## Dashboard header

- **API status** — `API connected`, `Checking API…`, or `API unreachable — retry` (click to check again).
- **Theme toggle** — shows the current mode: **Auto**, **Light** or **Dark**. On a first visit the mode is Auto, which follows the operating system's light/dark setting. Clicking switches to the opposite of the current look (Light ↔ Dark) and remembers the choice in the browser; the button does not return to Auto (clear the site's stored data to get Auto back).

## Sidebar

The sidebar has two numbered sections. The views below it use these settings.

### 01 API settings

- **Falcon API base URL** — where the dashboard sends requests. Empty (placeholder "same origin (/api)") means the dashboard's own address, which is the normal setup. Type another URL and press **Apply** to switch servers; the inventory reloads. When the value differs from the build default, a hint shows the build default.
- **Inventory** — number of inventory files and the earliest and latest dates in the data.

### 02 Load settings

- **Category** — loads every retailer of one category (for example `Markets`, `ClothingStores`, `HousesRent`). On a first visit the category is **Markets**; afterwards the dashboard opens on the last category you chose (remembered in the browser). Typing filters the list.
- **Retailers to load (N)** — the retailers actually loaded. Choosing a category fills it; you can then remove retailers or add ones from other categories. Once the selection no longer matches a category exactly, the Category field shows "Custom selection". Search tolerates Turkish characters, prefixes, substrings and small typos.
- **Start date / End date** — the date window for all views except EpeyKatfg monthly. Defaults to the last 60 days of data (never before the earliest date).
- **Load all files in date range** — **on by default**: every snapshot file in the date window is used. A note under it says the dashboard sends `all_history=true` and `max_files=0`.
- **Max CSV files per retailer** — slider from 10 to 160 (default 45), only active when "Load all files" is off. Uses the newest files in the date window; lower it for faster loading.

The footer shows how many common query parameters are prepared for the data requests.

## Views

Choose a view with the **Explore** tabs (arrow keys, Home and End also move between tabs).

### 1. Product price explorer

Pick a **Retailer** and a **Product** (both searchable; the lists show the products seen at the loaded retailers in the date window). Shows metric cards for latest price, cheapest price, cheapest date and change since first observation; a **Monthly average price** chart over the product's complete history (independent of the date window); and a **Daily price history** section with a **Show daily chart** toggle (off by default) and the raw observation table for the selected date window. Categories recorded as `Uncategorized` are shown as "—".

> **Changed 2026-10-17:** the product lists load from a lighter request, so they now work for large categories such as Markets; previously loading them could fail with "API response from /api/history was not valid JSON". See [change history](README.md#change-history).

### 2. Retailer average price chart

Compare price trends across the loaded retailers. Choose which retailers to plot and **Average** or **Median** aggregation. Shows a line chart and the data table.

### 3. Biggest price movers

Choose a **Retailer scope** (all loaded retailers or one) and the number of rows (slider, 5–30). Shows the biggest drops versus each product's peak price and the biggest gains since first observation. Only products seen on at least two dates count.

### 4. Dataset coverage overview

Totals for retailers, products, observations and the date range; a chart of tracked products over time; a chart of the top 20 categories by tracked products; and a warning if files were skipped (with the current database this list is always empty).

### 5. EpeyKatfg monthly inflation

Month-over-month inflation from the EpeyKatfg artifact: cards for months covered, latest month, latest average inflation, latest TÜİK-weighted change, mean monthly average and covered TÜİK weight; a line chart; and the monthly table. This view ignores the sidebar filters.

## Tips

- The first request for a new combination of retailers and dates can take a few seconds; repeating it is fast because the API caches results for 5 minutes.
- Large categories (for example `HousesRent`) with "Load all files" on can produce big responses. Narrow the date window, remove retailers, or turn "Load all files" off and lower the file cap.

## Troubleshooting

- **"API unreachable"** or a network error: the API is not running, or the API URL in the sidebar is wrong. Clear the URL to use the same origin, or set the correct one and press Apply.
- **"Database not found; run scripts/build_database.py"**: the API has no database yet; whoever runs the API must build it (see [GETTING-STARTED.md](GETTING-STARTED.md)).
- **"Database predates the catalog; run scripts/build_database.py"** on the shop pages: the database was built before the shop existed. The dashboard at `/analiz` still works; rebuild the database to enable the shop.
- **EpeyKatfg monthly view is empty:** the monthly inflation file is missing on the API side.
