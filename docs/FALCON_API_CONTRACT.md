# Falcon REST API Contract & Specification

**Target Frontend:** Svelte 5 / SvelteKit SPA (`frontend/`)  
**API Backend:** Falcon WSGI application (`inflation_dashboard/api/falcon_app.py`)  
**Specification Version:** 2.1.0  
**Last Updated:** 2026-10-20  
**Status:** Authoritative. [API.md](API.md) is a summary; this file wins on any difference.

---

## 1. Transport

- **Protocol:** HTTP/1.1 through a WSGI server (Granian, Gunicorn or Waitress; see [CONFIGURATION.md](CONFIGURATION.md)). Only `GET` routes exist.
- **Base URL:** the SPA calls same-origin `/api/...` unless `VITE_API_BASE_URL` was set at build time.
- **Content-Type:** `application/json`, UTF-8.
- **Serialization:** `orjson`. `NaN`, `Infinity`, `NaT` and pandas/numpy scalars are converted to JSON-native values (`null` for missing) before encoding.
- **CORS:** `falcon.CORSMiddleware` with `FALCON_CORS_ORIGINS` (default `*`). It adds `Access-Control-Allow-Origin` (`*`, or the request's origin when `FALCON_CORS_ORIGINS` is a list) to every response, including errors, whose request carries an allowed `Origin` header; requests without `Origin` get no CORS headers. Preflight `OPTIONS` returns `200` with `Access-Control-Allow-Methods: GET`, `Access-Control-Allow-Headers` echoing `Access-Control-Request-Headers` (`*` when absent) and `Access-Control-Max-Age: 86400`. No headers are exposed (`ETag` is not readable cross-origin from JavaScript, but the browser cache still uses it).
- **Data source:** the read-only SQLite database built by `scripts/build_database.py` (see [DATABASE.md](DATABASE.md)); `/api/epeykatfg/monthly-inflation` reads a CSV artifact (see [DATA_CONTRACT.md](DATA_CONTRACT.md)). Architecture and layer rules are in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 2. Envelope and errors

### 2.1 Envelope

Every response body, success or error, is:

```json
{
  "data": null,
  "meta": {},
  "errors": []
}
```

| Property | Type | Description |
|---|---|---|
| `data` | `object \| array \| null` | The payload. `null` on every error response. |
| `meta` | `object` | Filter reflection, counts and warnings on success; error context (for example the rejected filters) on error. Always an object. |
| `errors` | `array<{code, message}>` | Empty on success; exactly one error object on failure. |

The only responses without this body are `304 Not Modified` (no body) and CORS preflight `OPTIONS` (empty body).

### 2.2 Error object

```json
{
  "data": null,
  "meta": {"filters": {"retailer": ["NonExistentRetailer"]}},
  "errors": [{"code": "invalid_filter", "message": "Unknown retailer: NonExistentRetailer"}]
}
```

Error objects have exactly two fields, `code` and `message`. Context goes on the envelope's `meta`, not inside the error.

### 2.3 Error codes and status

| Status | `code` | When | `message` |
|---|---|---|---|
| 400 | `invalid_filter` | Any query-parameter validation failure (sections 3–4) | Names the parameter, e.g. `Invalid limit`, `Unknown retailer: X`, `Invalid date range` |
| 404 | `not_found` | Unknown route, `/api/product` found no product, or `/api/catalog/item` found no item | `Product not found: <key>` for products; `Item not found: <key>` for catalog items; Falcon's description or title for routes |
| 405 | `method_not_allowed` | A method other than `GET`/`OPTIONS` on a known route (the `Allow` header is `GET, OPTIONS`) | Falcon's description or title |
| other 4xx/5xx | `http_error` | Any other `falcon.HTTPError` raised by Falcon | Falcon's description or title |
| 500 | `server_error` | Any unhandled exception | Always the fixed string `Internal server error`; the traceback is logged server-side (logger `inflation_dashboard.api`), never sent |
| 503 | `database_unavailable` | The configured database file is missing or 0 bytes (every endpoint except `/api/health` and `/api/epeykatfg/monthly-inflation`) | `Database not found; run scripts/build_database.py` |
| 503 | `database_outdated` | `/api/catalog/*` only: the database was built before the catalog columns (`products.name_key`, `previous_price`, `price_since`, `is_current`, `is_store_latest`) existed. The other endpoints keep working; rebuild the database. | `Database predates the catalog; run scripts/build_database.py` |

The handlers for 404/405/500/503 are registered in `create_app`. Messages are short and safe to show in the UI.

---

## 3. Common filter parameters

`/api/history`, `/api/retailer-averages`, `/api/movers` and `/api/coverage` share these parameters (`parse_common_filters` in `inflation_dashboard/api/filters.py`).

| Parameter | Type | Default | Validation and behaviour |
|---|---|---|---|
| `retailer` | `string`, repeatable | `DEFAULT_RETAILERS`: `Markets / Gurmar`, `ClothingStores / Vakko`, `HomeGoods` (those present in the inventory; if none are, the first three inventory retailers) | Every value must be an inventory retailer, else 400 `Unknown retailer: <name>`. Repeat for several: `?retailer=A&retailer=B`. |
| `start_date` | `YYYY-MM-DD` | 60 days before the inventory `max_date`, but not before `min_date` | 400 `Invalid date` if unparseable; 400 `Invalid date range` if after `end_date`. |
| `end_date` | `YYYY-MM-DD` | inventory `max_date` | 400 `Invalid date` if unparseable. |
| `max_files` | integer ≥ 0 | `45` (`DEFAULT_MAX_FILES_PER_RETAILER`) | Newest N snapshot dates per retailer inside the date window. `0` means no cap. 400 `Invalid max_files` if negative or not an integer. |
| `all_history` | boolean | `false` | Accepts `1, true, t, yes, y, on` / `0, false, f, no, n, off` (case-insensitive). `true` (or `max_files=0`) sets the effective cap to 0, reports `all_history: true` and adds a warning. It does **not** widen the date window. 400 `Invalid all_history` otherwise. |

### Common response `meta`

```json
{
  "filters": {
    "selected_retailers": ["Markets / Gurmar"],
    "start_date": "2026-08-18",
    "end_date": "2026-10-17",
    "max_files_per_retailer": 2,
    "all_history": false
  },
  "inventory_file_count": 10490,
  "selected_inventory_file_count": 2,
  "history_row_count": 8685,
  "skipped_file_count": 0,
  "warnings": []
}
```

`selected_inventory_file_count` counts the source snapshots matching the filters. `skipped_file_count` is always `0` with the SQLite adapter (skipped files are a build-time concept).

### Warnings (`meta.warnings`)

| Warning | Added when |
|---|---|
| `all_history requested; history load is uncapped` | `all_history=true` or `max_files=0` |
| `history response may be large` | `/api/history` general mode, when `all_history` is on or more than 5000 rows are returned |
| `selected files skipped; no usable rows loaded` | history is empty, files were reported skipped and the selection matched files. The SQLite adapter never reports skipped files, so this does not occur today. |

---

## 4. Endpoints

### 4.1 `GET /api/health`

Lightweight probe; never touches inventory or history. Always 200 (unless the server itself fails). `data.database` reports whether the configured database file exists and is non-empty.

```json
{
  "data": {"status": "ok", "database": "available"},
  "meta": {"service": "inflation-dashboard-api"},
  "errors": []
}
```

`database` is `"unavailable"` when data endpoints would return 503. Health responses are not cached.

### 4.2 `GET /api/inventory`

Retailers and the overall date range. No parameters.

```json
{
  "data": {
    "retailers": ["Alcohol Tobacco / AlkolFiyatlari", "…", "Markets / Gurmar", "…"],
    "min_date": "2023-09-06T00:00:00",
    "max_date": "2026-10-17T00:00:00"
  },
  "meta": {
    "file_count": 10490,
    "inventory_file_count": 10490
  },
  "errors": []
}
```

- `retailers` is sorted. `min_date`/`max_date` are full ISO datetimes (`…T00:00:00`), or `null` for an empty inventory.
- `meta.file_count` (and the duplicate `inventory_file_count`) is the number of ingested source snapshots. `meta` has no `warnings` key.

### 4.3 `GET /api/history`

Two modes:

1. **General** (`product_name` omitted): every observation matching the common filters.
2. **Product** (`product_name` given): one product's series inside the filtered history, plus a summary.

Parameters: the common filters, plus

- `product_name` (`string`, optional): exact product name.
- `product_retailer` (`string`, optional): retailer of that product. If omitted, exactly one retailer must be selected (it is used); otherwise 400 `product_retailer is required` (with `meta.filters.selected_retailers`).

**General mode**

```json
{
  "data": {
    "history": [
      {
        "date": "2026-10-17T00:00:00",
        "retailer": "Markets / Gurmar",
        "product_id": "1000 Cc Cam Kavanoz",
        "product_name": "1000 Cc Cam Kavanoz",
        "category": "Uncategorized",
        "price": 19.99,
        "source_file": "Markets_Gurmar.json#2026-10-17"
      }
    ]
  },
  "meta": {
    "filters": {"selected_retailers": ["Markets / Gurmar"], "start_date": "2026-08-18", "end_date": "2026-10-17", "max_files_per_retailer": 2, "all_history": false},
    "inventory_file_count": 10490,
    "selected_inventory_file_count": 2,
    "history_row_count": 8685,
    "skipped_file_count": 0,
    "warnings": ["history response may be large"]
  },
  "errors": []
}
```

Rows are ordered by retailer, product name, date. `source_file` is the JSON partition's file name and date (`Markets_Gurmar.json#2026-10-17`, a file in `data/prices_json/`), which is every retailer today; a retailer built from raw CSVs would show the CSV's path relative to `data/` (`raw/01_Food/...`).

**Product mode**

```json
{
  "data": {
    "history": [
      {"date": "2026-10-16T00:00:00", "price": 1349.9, "category": "Uncategorized", "source_file": "Markets_Gurmar.json#2026-10-16"},
      {"date": "2026-10-17T00:00:00", "price": 1349.9, "category": "Uncategorized", "source_file": "Markets_Gurmar.json#2026-10-17"}
    ],
    "summary": {
      "latest_price": 1349.9,
      "cheapest_price": 1349.9,
      "cheapest_date": "2026-10-16T00:00:00",
      "change_since_first_pct": 0.0
    }
  },
  "meta": {
    "filters": {"selected_retailers": ["Markets / Gurmar"], "start_date": "2026-08-18", "end_date": "2026-10-17", "max_files_per_retailer": 2, "all_history": false},
    "inventory_file_count": 10490,
    "selected_inventory_file_count": 2,
    "history_row_count": 8685,
    "skipped_file_count": 0,
    "warnings": [],
    "product_name": "Aptamil 1 Bebek Sütü 800 Gr",
    "product_retailer": "Markets / Gurmar"
  },
  "errors": []
}
```

`history_row_count` counts the whole filtered history, not the product's rows. An unknown product returns 200 with `history: []` and `summary` `{latest_price: null, cheapest_price: null, cheapest_date: null, change_since_first_pct: 0.0}`. Product mode adds no "large" warning.

### 4.4 `GET /api/retailer-averages`

Average or median price per retailer per snapshot date.

Parameters: the common filters, plus `aggregation` = `Average` (default) or `Median` (case-sensitive); anything else is 400 `Invalid aggregation`.

```json
{
  "data": {
    "records": [
      {"date": "2026-10-16T00:00:00", "retailer": "Markets / Gurmar", "price": 182.0973773889017},
      {"date": "2026-10-17T00:00:00", "retailer": "Markets / Gurmar", "price": 181.9625310916628}
    ],
    "retailer_averages": [
      {"date": "2026-10-16T00:00:00", "retailer": "Markets / Gurmar", "price": 182.0973773889017},
      {"date": "2026-10-17T00:00:00", "retailer": "Markets / Gurmar", "price": 181.9625310916628}
    ]
  },
  "meta": {"filters": {"…": "…"}, "…": "common meta", "aggregation": "Average", "skipped_file_count": 0},
  "errors": []
}
```

`data.retailer_averages` is a **duplicate** of `data.records` (the same list, kept for older clients). The SPA reads `records`.

### 4.5 `GET /api/movers`

Biggest drops from peak and biggest gains since first observation, for products seen on at least two dates.

Parameters: the common filters, plus

- `scope_retailer` (`string`, default `All retailers`): restrict to one selected retailer; anything else is 400 `Unknown retailer: <name>`.
- `limit` (integer 5–30, default 10): rows per list. Out of range or not an integer is 400 `Invalid limit` (not clamped).
- `mover_count` (integer 5–30): alias used as the default for `limit`; it is validated even when `limit` is given (400 `Invalid mover_count`).

```json
{
  "data": {
    "biggest_drops": [
      {"retailer": "Markets / Gurmar", "product_name": "Raid Elektro Likit Yedek Şişe", "latest_price": 143.96, "max_price": 399.9, "savings_vs_peak": 255.93999999999997, "drop_from_peak_pct": -64.00100025006252, "last_seen": "2026-10-17T00:00:00"}
    ],
    "biggest_gains": [
      {"retailer": "Markets / Gurmar", "product_name": "Duru Sabun Diamonds Series 4X90 Gr. Blue", "first_price": 89.9, "latest_price": 149.9, "change_since_first_pct": 66.74082313681868, "first_seen": "2026-10-15T00:00:00", "last_seen": "2026-10-17T00:00:00"}
    ]
  },
  "meta": {"filters": {"…": "…"}, "…": "common meta", "scope_retailer": "All retailers", "limit": 5, "eligible_product_count": 4353, "skipped_file_count": 0},
  "errors": []
}
```

### 4.6 `GET /api/coverage`

Observation volume over time and per category.

Parameters: the common filters, plus `category_limit` (integer ≥ 1, default 20, no maximum); otherwise 400 `Invalid category_limit`.

```json
{
  "data": {
    "summary": {
      "retailer_count": 1,
      "product_count": 4342,
      "observation_count": 4342,
      "date_range": "2026-10-17 → 2026-10-17",
      "skipped_file_count": 0
    },
    "coverage_over_time": [
      {"date": "2026-10-17T00:00:00", "retailer": "Markets / Gurmar", "tracked_products": 4342}
    ],
    "category_coverage": [
      {"retailer": "Markets / Gurmar", "category": "Uncategorized", "products": 4342}
    ],
    "skipped_files": []
  },
  "meta": {"filters": {"…": "…"}, "…": "common meta", "category_limit": 2, "skipped_file_count": 0},
  "errors": []
}
```

`skipped_files` is a list of `{file, reason}` objects. With the SQLite adapter it is always empty and `skipped_file_count` is 0; files that failed to parse are reported by the database build instead.

### 4.7a `GET /api/products`

Distinct product names per retailer, for product pickers. The SPA's Product explorer uses it instead of downloading the full history (which can exceed the browser's maximum string size for a large category).

Parameters:

- `retailer` (`string`, repeatable, **required**): every value must be an inventory retailer. Missing → 400 `retailer is required`; unknown → 400 `Unknown retailer: <name>`.
- `start_date`, `end_date` (`YYYY-MM-DD`, optional, no defaults): only products observed inside the window are listed (their first/last observation overlaps it). Unparseable → 400 `Invalid date`; start after end → 400 `Invalid date range`.

`data` is one object per retailer that has matching products, sorted by retailer, with names sorted (SQLite binary order). Cached and compressed like the other endpoints (§5); 503 without a database.

```json
{
  "data": [
    {"retailer": "Markets / Gurmar", "products": ["1000 Cc Cam Kavanoz", "…"]},
    {"retailer": "Markets / Onur", "products": ["…"]}
  ],
  "meta": {"retailers": ["Markets / Gurmar", "Markets / Onur"], "start_date": "2026-08-18", "end_date": "2026-10-17", "product_count": 102643},
  "errors": []
}
```

### 4.7 `GET /api/products/search`

Product autocomplete over the `product_prices` view. Not used by the SPA.

Parameters:

- `q` (or `query`) (`string`, optional): substring match on `product_name` or `product_id` (SQL `LIKE '%q%'`, case-insensitive for ASCII letters only). Empty returns the top products.
- `retailer` (`string`, optional): exact retailer filter (not validated against the inventory).
- `category` (`string`, optional): exact category filter.
- `limit` (integer 1–100, default 20): out of range or not an integer is 400 `invalid_filter` `Invalid limit` (not clamped).

Results are ordered by `observations_count` descending, then `product_name`. If the query itself fails, `data` is `[]` (the error is swallowed).

```json
{
  "data": [
    {
      "product_id": "Aptamil 1 Bebek Sütü 800 Gr",
      "retailer": "Markets / Gurmar",
      "product_name": "Aptamil 1 Bebek Sütü 800 Gr",
      "category": "Uncategorized",
      "first_date": "2026-02-21",
      "last_date": "2026-10-17",
      "latest_price": 1349.9,
      "min_price": 899.9,
      "max_price": 1349.9,
      "observations_count": 220
    }
  ],
  "meta": {"query": "Aptamil", "retailer": null, "category": null, "limit": 1, "count": 1},
  "errors": []
}
```

### 4.8 `GET /api/product`

One product's summary and its complete price history (not limited by any date filter).

Parameters:

- `product_id` (`string`) or `product_name` (`string`): one is required (400 `product_id or product_name is required`). **When `product_id` is given, `product_name` is ignored.**
- `retailer` (`string`, optional).

Lookup: the key is matched against `product_id`, then against `product_name`. With `retailer`, only that retailer is searched (if several of its products share the `product_name`, which one is returned is arbitrary); without it, the match with the most observations wins. No match (or a database error during lookup) returns 404 `not_found` with message `Product not found: <key>` and `meta` `{product_id, product_name, retailer}` echoing the request.

```json
{
  "data": {
    "product_id": "Aptamil 1 Bebek Sütü 800 Gr",
    "retailer": "Markets / Gurmar",
    "product_name": "Aptamil 1 Bebek Sütü 800 Gr",
    "category": "Uncategorized",
    "first_date": "2026-02-21",
    "last_date": "2026-10-17",
    "latest_price": 1349.9,
    "min_price": 899.9,
    "max_price": 1349.9,
    "observations_count": 220,
    "price_history": {"2026-02-21": 1109.9, "2026-02-22": 1109.9, "…": "…", "2026-10-17": 1349.9},
    "history": [
      {"date": "2026-02-21", "price": 1109.9, "category": "Uncategorized", "source_file": ""},
      {"date": "2026-02-22", "price": 1109.9, "category": "Uncategorized", "source_file": ""}
    ],
    "summary": {
      "latest_price": 1349.9,
      "cheapest_price": 899.9,
      "cheapest_date": "2026-03-19",
      "change_since_first_pct": 21.623569690963148
    }
  },
  "meta": {"product_id": "Aptamil 1 Bebek Sütü 800 Gr", "retailer": "Markets / Gurmar", "observations_count": 220},
  "errors": []
}
```

- `price_history` maps `YYYY-MM-DD` to price; `history` is the same data as a date-sorted array. In `history`, `date` is a plain date (not a datetime), `category` is the product's current category and `source_file` is always `""`.
- `summary.cheapest_date` is the first date at `min_price`; `change_since_first_pct` compares `latest_price` with the first observed price (`0.0` when there is no first price).

### 4.9 `GET /api/epeykatfg/monthly-inflation`

The EpeyKatfg month-over-month inflation artifact (`EPEYKATFG_MONTHLY_CSV`, default `data/inflation/EpeyKatfg/monthly_inflation.csv`). Does not need the database.

- `data`: one object per CSV row, keyed by the CSV header. `month`, `prev_month` and `groups` are strings; every other value that parses as a number is a number (counts such as `n_matched` arrive as floats, e.g. `642.0`).
- Columns today: `month`, `prev_month`, `n_matched`, `avg_inflation`, `basic_index`, `median_inflation_nonzero`, `pct_increased`, `pct_decreased`, `pct_unchanged`, `tuik_weighted`, `covered_weight`, `groups`, then `n_<code>`, `avg_<code>`, `basic_<code>` per TÜİK group.
- `meta`: `count` (rows), `columns` (header), `source` and `notes` (fixed description strings).
- A missing or header-less file returns 200 with `data: []`, `count: 0`, `columns: []`.

### 4.10 `GET /api/catalog/groups`

Groups of the price-comparison catalog and their stores, for the shop's navigation. No parameters.

The four catalog endpoints (§4.10–§4.13) read the `products` table through `inflation_dashboard/adapters/sqlite_catalog_repository.py`:

- A retailer label `Group / Store` is split into its group and store (`Markets / Migros` → `Markets`, `Migros`); a label without ` / ` (`EpeyKatfg`) is its own group and store.
- The `HousesRent` group (rental listings, `CATALOG_EXCLUDED_GROUPS`) is never part of the catalog.
- Groups, search and deals count only current offers (`products.is_current = 1`, see [DATABASE.md](DATABASE.md#catalog-columns)).
- They are cached and compressed like the other endpoints (§5), return 503 `database_unavailable` without a database and 503 `database_outdated` when the database was built before the catalog columns existed (§2.3).

`data` lists groups with at least one current offer, largest `offer_count` first (ties by name); each group's `stores` are sorted the same way and list only stores with current offers. `last_date` is the newest `last_date` of any product (current or not) of the store, and for a group, of its listed stores. `meta.count` is the number of groups.

```json
{
  "data": [
    {
      "group": "Cosmetics",
      "offer_count": 101890,
      "last_date": "2026-10-17",
      "stores": [
        {"store": "BeymenBeauty", "retailer": "Cosmetics / BeymenBeauty", "offer_count": 19311, "last_date": "2026-10-16"},
        {"store": "Gratis", "retailer": "Cosmetics / Gratis", "offer_count": 13019, "last_date": "2026-10-16"}
      ]
    }
  ],
  "meta": {"count": 13},
  "errors": []
}
```

### 4.11 `GET /api/catalog/search`

Searches catalog items. An **item** is every product that shares one `products.name_key` (the Turkish-aware normalized product name from `inflation_dashboard/domain/catalog.py`), so one item groups the same product across stores; each product is one store's **offer**.

Parameters:

- `q` (`string`, optional): normalized with the same `name_key` rules and split into terms; every term must occur as a substring of the item's `name_key`. Empty lists every item.
- `group`, `store` (`string`, optional, exact match; blank is ignored): limit the offers to one group and/or store. Unknown values are not an error; they return `data: []` and `total: 0`.
- `sort` (default `relevance`): `relevance` ranks by the number of query terms that match whole words, then store count, then shorter names; `price_asc` / `price_desc` by `min_price`; `drop` by `max_drop_percent` (items without a drop last), then store count. Any other value → 400 `Invalid sort`.
- `limit` (integer 1–60, default 24), `offset` (integer 0–10000, default 0): out of range or not an integer → 400 `Invalid limit` / `Invalid offset` (not clamped).

Only current offers with `latest_price > 0` in the selected group/store count, and of those only each store's latest prices for the item (`products.is_store_latest = 1`: offers last seen on the store's newest date for that item; see [DATABASE.md](DATABASE.md#catalog-columns)), matching the per-store prices of §4.12. For each item, `name`, `store` and `category` come from its cheapest offer; `stores` lists up to three stores, cheapest first; `min_price`/`max_price` span the offers; `max_drop_percent` is the largest offer `drop_percent` (§4.12), `null` if none dropped; `last_date` is the newest offer date. `meta.total` counts every matching item (`0` when `offset` is past the last match), `meta.count` the items on this page.

```json
{
  "data": [
    {
      "key": "içim yarım yağlı süt 1l",
      "name": "İçim Yarım Yağlı Süt 1 L",
      "group": "Markets",
      "category": "Süt, Kahvaltılık",
      "store": "Hapeloglu",
      "stores": ["Hapeloglu", "BizimMarket", "CarrefourSA"],
      "offer_count": 5,
      "store_count": 5,
      "min_price": 55.0,
      "max_price": 59.75,
      "max_drop_percent": null,
      "last_date": "2026-10-17"
    }
  ],
  "meta": {"query": "süt 1l", "group": null, "store": null, "sort": "relevance", "limit": 1, "offset": 0, "count": 1, "total": 322},
  "errors": []
}
```

### 4.12 `GET /api/catalog/item`

One item's offers in every store, each with its full price history.

Parameters:

- `key` (`string`, **required**): a `name_key`, as returned in `key` by §4.11. Missing or blank → 400 `key is required`. A key with no products → 404 `not_found` with message `Item not found: <key>` and `meta` `{key}`.

`offers` holds **one offer per store** for the products with that `name_key` outside `HousesRent`, **including stale ones** (`is_current: false`): current offers first, then cheapest first, at most 40 stores (`MAX_ITEM_OFFERS`; up to 400 products are read, `MAX_ITEM_ROWS`). A store's offer is its latest price: of its products, those with the newest `last_date`, and among them the cheapest (a product without a price never wins over a priced one). Each offer is the `products` row plus:

- `retailer`, `group`, `store`: the retailer label and its split.
- `previous_price`, `price_since`: the price before the latest change and the first day of the current price (see [DATABASE.md](DATABASE.md#catalog-columns)).
- `is_current`: a boolean.
- `drop_percent`: `(previous_price − latest_price) / previous_price × 100`, rounded to 2 decimals, when the latest change was a drop; else `null`.
- `history`: every observation as `[date, price]` pairs, oldest first.
- `other_offers`: the store's other products for the item (another product under the same name, such as a different repair service for the same phone, or an older offer), newest `last_date` first, then cheapest first. Same fields, without `history` and `other_offers`; `[]` when the store has only one.

`name`, `group` and `category` come from the cheapest current offer with a price (else the cheapest priced offer, else the first offer). In `summary`, `min_price`/`max_price` span the current offers with a price (all offers with a price when none is current); `lowest_ever` is the lowest price in any returned offer's history, with its date and store, ignoring prices below 25 % (`LOWEST_EVER_FLOOR`) of the lowest current price (`null` when nothing qualifies); `store_count` counts distinct retailers among the returned offers, which equals `offer_count` now that there is one offer per store; `offer_count` and `current_offer_count` count the returned (per-store) offers, so `other_offers` are not counted and `lowest_ever` ignores their histories. `meta` is `{key, offer_count}`.

```json
{
  "data": {
    "key": "içim yarım yağlı süt 1l",
    "name": "İçim Yarım Yağlı Süt 1 L",
    "group": "Markets",
    "category": "Kazandıran Ürünler > Süt ve Süt Ürünleri",
    "offers": [
      {
        "retailer": "Markets / BizimMarket",
        "group": "Markets",
        "store": "BizimMarket",
        "product_id": "13488",
        "product_name": "İçim Yarım Yağlı Süt 1 L",
        "name_key": "içim yarım yağlı süt 1l",
        "category": "Kazandıran Ürünler > Süt ve Süt Ürünleri",
        "latest_price": 54.5,
        "previous_price": 59.5,
        "price_since": "2026-10-19",
        "first_date": "2026-10-05",
        "last_date": "2026-10-19",
        "min_price": 54.5,
        "max_price": 59.5,
        "observations_count": 6,
        "is_current": true,
        "drop_percent": 8.4,
        "other_offers": [
          {
            "retailer": "Markets / BizimMarket",
            "group": "Markets",
            "store": "BizimMarket",
            "product_id": "İçim Yarım Yağlı Süt 1 L",
            "product_name": "İçim Yarım Yağlı Süt 1 L",
            "name_key": "içim yarım yağlı süt 1l",
            "category": "Uncategorized",
            "latest_price": 43.9,
            "previous_price": 52.5,
            "price_since": "2026-04-10",
            "first_date": "2026-03-14",
            "last_date": "2026-04-10",
            "min_price": 1.0,
            "max_price": 52.5,
            "observations_count": 22,
            "is_current": false,
            "drop_percent": 16.38
          }
        ],
        "history": [["2026-10-05", 59.5], ["2026-10-06", 59.5], "…", ["2026-10-19", 54.5]]
      }
    ],
    "summary": {
      "offer_count": 5,
      "current_offer_count": 5,
      "store_count": 5,
      "min_price": 54.5,
      "max_price": 59.75,
      "lowest_ever": {"price": 49.5, "date": "2026-10-02", "store": "Hapeloglu"},
      "last_date": "2026-10-19"
    }
  },
  "meta": {"key": "içim yarım yağlı süt 1l", "offer_count": 5},
  "errors": []
}
```

BizimMarket's older listing (last seen 2026-04-10, with a `1.0` scraper error in its history) appears only under `other_offers`, so neither its price nor its history affects `summary`. The 25 % floor drops such scraper errors from the offers that are read.

### 4.13 `GET /api/catalog/deals`

Current offers whose latest price change was a drop, largest drop first (ties: more observations first).

Parameters:

- `group`, `store` (`string`, optional, exact match; blank is ignored): as in §4.11.
- `min_drop` (integer 1–80, default 5): minimum `drop_percent`.
- `days` (integer 1–365, default 30): the drop must have happened within this many days of the offer's last observation (`price_since` on or after `last_date` − `days`).
- `limit` (integer 1–60, default 24).

Out of range or not an integer → 400 `Invalid <name>` (not clamped). Drops above 80 % (`MAX_DEAL_DROP_PERCENT`, also the `min_drop` maximum) are ignored as likely scraper or unit errors.

`data` is a list of offers shaped as in §4.12 **without** `history` and `other_offers`. `meta` echoes `group`, `store`, `min_drop`, `days`, `limit` and adds `count`.

```json
{
  "data": [
    {
      "retailer": "ConstructionSuppliesMarkets / Bauhaus",
      "group": "ConstructionSuppliesMarkets",
      "store": "Bauhaus",
      "product_id": "ECA 3/4 Yaylı Çek Valf",
      "product_name": "ECA 3/4 Yaylı Çek Valf",
      "name_key": "eca 3 4 yaylı çek valf",
      "category": "Uncategorized",
      "latest_price": 50.0,
      "previous_price": 250.0,
      "price_since": "2026-10-12",
      "first_date": "2026-03-11",
      "last_date": "2026-10-16",
      "min_price": 50.0,
      "max_price": 250.0,
      "observations_count": 80,
      "is_current": true,
      "drop_percent": 80.0
    }
  ],
  "meta": {"group": null, "store": null, "min_drop": 5, "days": 30, "limit": 1, "count": 1},
  "errors": []
}
```

---

## 5. Caching and compression

Applies to the successful (200) responses of every endpoint except `/api/health`. Error responses are never cached.

- **Server cache:** the serialized body is cached in-process per endpoint and raw query string for 300 seconds (up to 512 entries and 1 GiB per worker). Identical requests are served from it without recomputation.
- **ETag:** a strong ETag (quoted MD5 of the body bytes) on every cacheable response. The gzip and plain variants have different ETags.
- **Conditional requests:** `If-None-Match` matching the current ETag (or `*`) returns `304 Not Modified` with the same `ETag`, `Cache-Control` and `Vary` headers and no body.
- **Cache-Control:** `public, max-age=300`.
- **Compression:** bodies of at least 1 KB (1024 bytes) also get a gzip variant. It is sent with `Content-Encoding: gzip` when `Accept-Encoding` allows gzip (q > 0). Whenever a gzip variant exists, the response carries `Vary: Accept-Encoding`, whichever variant was sent.

---

## 6. TypeScript types (`frontend/src/lib/types/api.ts`)

This section mirrors `frontend/src/lib/types/api.ts` as of 2026-10-18. The file in the repository is the source; if they differ, update this copy.

### 6.1 Differences between client types and server output

The client types are not a complete or exact model of the server. Known differences:

| Client type | Server behaviour |
|---|---|
| *(none)* `ProductSearchResult`, `ProductSearchMeta`, `ProductHistoryRecord` | No client types exist for `/api/products/search` because the SPA never calls it. The response shape is in §4.7. (`/api/products`, §4.7a, does have client types.) |
| `InventoryMeta.warnings` | Never sent: `/api/inventory` meta has only `file_count` and `inventory_file_count`. Listed under [Known issues](ARCHITECTURE.md#known-issues). |
| `ProductDetailMeta` fields `string \| null` | On a 200 response `product_id` and `retailer` are always strings; `null` only appears in the 404 error meta, which has a different shape. |
| `ApiError.meta?` | Never sent: error objects are `{code, message}`; context is on the envelope `meta`. |
| `HealthData` | Has no `database` field; the server also sends `database: "available" \| "unavailable"`. |
| `ProductDetailData.history: ProductHistoryPoint[]` | Product-detail history dates are plain `YYYY-MM-DD` and `source_file` is `""`, unlike `/api/history` product mode. |
| `CommonFilterMeta.warnings?`, `history_row_count?`, `skipped_file_count?` | Optional in the type, but always sent by the four filter endpoints. |
| *(none)* `meta` types for `/api/catalog/groups`, `/api/catalog/item`, `/api/catalog/deals` | Only `/api/catalog/search` has a `meta` type (`CatalogSearchMeta`); the SPA does not read the other catalog `meta` objects. Their shapes are in §4.10, §4.12 and §4.13. |
| `CatalogOffer.history?` | Sent by `/api/catalog/item` only; `/api/catalog/deals` offers have no `history`. |
| `CatalogOffer.other_offers?` | Always sent on `/api/catalog/item` offers (`[]` when the store has one product); never on deals, and the nested offers carry neither `history` nor `other_offers`. |

### 6.2 `api.ts`

```typescript
/**
 * The `{data, meta, errors}` envelope every endpoint returns.
 * `fetchApi` returns only `{data, meta}` on success.
 */
export interface ApiResponse<T, M = Record<string, unknown>> {
  data: T;
  meta: M;
  errors: ApiError[];
}

/**
 * One entry of `errors` on a failed response (any endpoint).
 * The server sends only `code` and `message`; `meta` is never sent (context is on the envelope's `meta`).
 */
export interface ApiError {
  code: string;
  message: string;
  meta?: Record<string, unknown>;
}

/**
 * Envelope of any error response (4xx/5xx): `data` is null and `errors` holds one entry.
 */
export interface ApiErrorEnvelope {
  data: null;
  meta: Record<string, unknown>;
  errors: ApiError[];
}

// ── Common Filter Parameters ──────────────────────────────────────────────────

/** Common filter query parameters of `/api/history`, `/api/retailer-averages`, `/api/movers` and `/api/coverage`. */
export interface CommonFilterParams {
  retailer?: string | string[];
  start_date?: string; // YYYY-MM-DD
  end_date?: string; // YYYY-MM-DD
  max_files?: number;
  all_history?: boolean;
}

/**
 * `meta` shared by the four filter endpoints (`/api/history`, `/api/retailer-averages`, `/api/movers`, `/api/coverage`).
 * The optional fields are in fact always sent by those endpoints.
 */
export interface CommonFilterMeta {
  filters: {
    selected_retailers: string[];
    start_date: string | null;
    end_date: string | null;
    max_files_per_retailer: number;
    all_history: boolean;
  };
  inventory_file_count: number;
  selected_inventory_file_count: number;
  history_row_count?: number;
  skipped_file_count?: number;
  warnings?: string[];
}

// ── 1. Health ─────────────────────────────────────────────────────────────────

/** `data` of `GET /api/health`. The server also sends `database: "available" | "unavailable"`, not modelled here. */
export interface HealthData {
  status: 'ok' | string;
}

/** `meta` of `GET /api/health`. */
export interface HealthMeta {
  service: string;
}

/** Full `GET /api/health` response. */
export type HealthResponse = ApiResponse<HealthData, HealthMeta>;

// ── 2. Inventory ──────────────────────────────────────────────────────────────

/** `data` of `GET /api/inventory`: sorted retailers and the overall date range (ISO datetimes). */
export interface InventoryData {
  retailers: string[];
  min_date: string | null; // ISO datetime/date
  max_date: string | null; // ISO datetime/date
}

/**
 * `meta` of `GET /api/inventory`.
 * `warnings` is never sent by the server (listed under Known issues in docs/ARCHITECTURE.md).
 */
export interface InventoryMeta {
  file_count: number;
  inventory_file_count: number;
  warnings?: string[];
}

/** Full `GET /api/inventory` response. */
export type InventoryResponse = ApiResponse<InventoryData, InventoryMeta>;

// ── 3. History ────────────────────────────────────────────────────────────────

/** One observation row of `GET /api/history` in general mode (no `product_name`). */
export interface HistoryRecord {
  date: string; // ISO datetime: "2026-09-02T00:00:00"
  retailer: string;
  product_id: string | null;
  product_name: string;
  category: string | null;
  price: number | null;
  source_file: string;
}

/**
 * One point of a product series: `GET /api/history` product mode, and `history` of `GET /api/product`.
 * From `/api/product`, `date` is a plain `YYYY-MM-DD` and `source_file` is `""`.
 */
export interface ProductHistoryPoint {
  date: string;
  price: number | null;
  category: string | null;
  source_file: string;
}

/** Product metrics in `GET /api/history` product mode and `GET /api/product`. */
export interface ProductSummary {
  latest_price: number | null;
  cheapest_price: number | null;
  cheapest_date: string | null;
  change_since_first_pct: number;
}

/** `data` of `GET /api/history` without `product_name`. */
export interface GeneralHistoryData {
  history: HistoryRecord[];
}

/** `data` of `GET /api/history` with `product_name`. */
export interface ProductHistoryData {
  history: ProductHistoryPoint[];
  summary: ProductSummary;
}

/** `meta` of `GET /api/history`; `product_name`/`product_retailer` are set in product mode. */
export interface HistoryMeta extends CommonFilterMeta {
  product_name?: string;
  product_retailer?: string;
}

/** Full `GET /api/history` response (either mode). */
export type HistoryResponse = ApiResponse<GeneralHistoryData | ProductHistoryData, HistoryMeta>;

// ── 4. Retailer Averages ──────────────────────────────────────────────────────

/** One `{date, retailer, price}` point of `GET /api/retailer-averages`. */
export interface RetailerAverageRecord {
  date: string;
  retailer: string;
  price: number | null;
}

/** `data` of `GET /api/retailer-averages`; `retailer_averages` duplicates `records`. */
export interface RetailerAveragesData {
  records: RetailerAverageRecord[];
  retailer_averages: RetailerAverageRecord[];
}

/** `meta` of `GET /api/retailer-averages`. */
export interface RetailerAveragesMeta extends CommonFilterMeta {
  aggregation: 'Average' | 'Median';
}

/** Full `GET /api/retailer-averages` response. */
export type RetailerAveragesResponse = ApiResponse<RetailerAveragesData, RetailerAveragesMeta>;

// ── 5. Movers ─────────────────────────────────────────────────────────────────

/** One row of `biggest_drops` in `GET /api/movers` (drop from peak price). */
export interface MoverDropRecord {
  retailer: string;
  product_name: string;
  latest_price: number | null;
  max_price: number | null;
  savings_vs_peak: number | null;
  drop_from_peak_pct: number | null;
  last_seen: string | null;
}

/** One row of `biggest_gains` in `GET /api/movers` (gain since first observation). */
export interface MoverGainRecord {
  retailer: string;
  product_name: string;
  first_price: number | null;
  latest_price: number | null;
  change_since_first_pct: number | null;
  first_seen: string | null;
  last_seen: string | null;
}

/** `data` of `GET /api/movers`. */
export interface MoversData {
  biggest_drops: MoverDropRecord[];
  biggest_gains: MoverGainRecord[];
}

/** `meta` of `GET /api/movers`. */
export interface MoversMeta extends CommonFilterMeta {
  scope_retailer: string;
  limit: number;
  eligible_product_count: number;
}

/** Full `GET /api/movers` response. */
export type MoversResponse = ApiResponse<MoversData, MoversMeta>;

// ── 6. Coverage ───────────────────────────────────────────────────────────────

/** `data.summary` of `GET /api/coverage`. */
export interface CoverageSummary {
  retailer_count: number;
  product_count: number;
  observation_count: number;
  date_range: string;
  skipped_file_count: number;
}

/** One row of `coverage_over_time` in `GET /api/coverage`. */
export interface CoverageOverTimeRecord {
  date: string;
  retailer: string;
  tracked_products: number;
}

/** One row of `category_coverage` in `GET /api/coverage`. */
export interface CategoryCoverageRecord {
  retailer: string;
  category: string;
  products: number;
}

/** One row of `skipped_files` in `GET /api/coverage` (always empty with the SQLite database). */
export interface SkippedFileDiagnostic {
  file: string;
  reason: string;
}

/** `data` of `GET /api/coverage`. */
export interface CoverageData {
  summary: CoverageSummary;
  coverage_over_time: CoverageOverTimeRecord[];
  category_coverage: CategoryCoverageRecord[];
  skipped_files: SkippedFileDiagnostic[];
}

/** `meta` of `GET /api/coverage`. */
export interface CoverageMeta extends CommonFilterMeta {
  category_limit: number;
}

/** Full `GET /api/coverage` response. */
export type CoverageResponse = ApiResponse<CoverageData, CoverageMeta>;

// ── Product list ──────────────────────────────────────────────────────────────

/** One retailer's product names in `GET /api/products` (`data` is an array of these). */
export interface ProductListGroup {
  retailer: string;
  products: string[];
}

/** `meta` of `GET /api/products`. */
export interface ProductListMeta {
  retailers: string[];
  start_date: string | null;
  end_date: string | null;
  product_count: number;
}

/** Full `GET /api/products` response. */
export type ProductListResponse = ApiResponse<ProductListGroup[], ProductListMeta>;

// ── 7. Product Detail (SQLite-backed) ───────────────────────────────────────

/** `data` of `GET /api/product`: product summary, `price_history` map and `history` array. */
export interface ProductDetailData {
  product_id: string | null;
  retailer: string | null;
  product_name: string | null;
  category: string | null;
  first_date: string | null;
  last_date: string | null;
  latest_price: number | null;
  min_price: number | null;
  max_price: number | null;
  observations_count: number;
  price_history: Record<string, number>; // {date: price}
  history: ProductHistoryPoint[];
  summary: ProductSummary;
}

/** `meta` of `GET /api/product`. On a 200 response the fields are always strings (never null). */
export interface ProductDetailMeta {
  product_id: string | null;
  retailer: string | null;
  observations_count: number;
}

/** Full `GET /api/product` response. */
export type ProductDetailResponse = ApiResponse<ProductDetailData, ProductDetailMeta>;

// ── EpeyKatfg monthly inflation ──────────────────────────────────────────────

/** One month row of `GET /api/epeykatfg/monthly-inflation` (a row of the CSV artifact). */
export interface MonthlyInflationRecord {
  month: string; // YYYY-MM
  prev_month: string;
  n_matched: number;
  avg_inflation: number | null;
  basic_index: number | null;
  median_inflation_nonzero: number | null;
  pct_increased: number | null;
  pct_decreased: number | null;
  pct_unchanged: number | null;
  tuik_weighted: number | null;
  covered_weight: number | null;
  groups: string;
  [key: string]: unknown; // per-group columns: n_<code>, avg_<code>, basic_<code>
}

/** `meta` of `GET /api/epeykatfg/monthly-inflation`. */
export interface MonthlyInflationMeta {
  count: number;
  columns: string[];
  source: string;
  notes: string;
}

/** Full `GET /api/epeykatfg/monthly-inflation` response. */
export type MonthlyInflationResponse = ApiResponse<MonthlyInflationRecord[], MonthlyInflationMeta>;

// ── Price-comparison catalog ─────────────────────────────────────────────────

/** One store of a catalog group in `GET /api/catalog/groups`. */
export interface CatalogStore {
  store: string;
  retailer: string;
  offer_count: number;
  last_date: string | null;
}

/** One group of `GET /api/catalog/groups` (retailer label prefix, e.g. `Markets`). */
export interface CatalogGroup {
  group: string;
  offer_count: number;
  last_date: string | null;
  stores: CatalogStore[];
}

/** Sort orders accepted by `GET /api/catalog/search`. */
export type CatalogSort = 'relevance' | 'price_asc' | 'price_desc' | 'drop';

/** One item (all offers sharing a `name_key`) of `GET /api/catalog/search`. */
export interface CatalogSearchItem {
  key: string;
  name: string; // name of the cheapest offer
  group: string;
  category: string;
  store: string; // store of the cheapest offer
  stores: string[]; // up to three stores, cheapest first
  offer_count: number;
  store_count: number;
  min_price: number;
  max_price: number;
  max_drop_percent: number | null;
  last_date: string | null;
}

/** `meta` of `GET /api/catalog/search`. */
export interface CatalogSearchMeta {
  query: string;
  group: string | null;
  store: string | null;
  sort: CatalogSort;
  limit: number;
  offset: number;
  count: number;
  total: number;
}

/** One store's offer, as returned by `GET /api/catalog/item` and `GET /api/catalog/deals`. */
export interface CatalogOffer {
  retailer: string;
  group: string;
  store: string;
  product_id: string;
  product_name: string;
  name_key: string;
  category: string;
  latest_price: number | null;
  previous_price: number | null;
  price_since: string | null;
  first_date: string | null;
  last_date: string | null;
  min_price: number | null;
  max_price: number | null;
  observations_count: number;
  is_current: boolean;
  drop_percent: number | null;
  history?: [string, number][]; // `GET /api/catalog/item` only
  /** `GET /api/catalog/item` only: the store's other offers for the item, without `history`. */
  other_offers?: CatalogOffer[];
}

/** `data` of `GET /api/catalog/item`. */
export interface CatalogItem {
  key: string;
  name: string;
  group: string;
  category: string;
  offers: CatalogOffer[];
  summary: {
    offer_count: number;
    current_offer_count: number;
    store_count: number;
    min_price: number | null;
    max_price: number | null;
    lowest_ever: { price: number; date: string; store: string } | null;
    last_date: string | null;
  };
}

/** Full `GET /api/catalog/search` response. */
export type CatalogSearchResponse = ApiResponse<CatalogSearchItem[], CatalogSearchMeta>;
```

---

## 7. Frontend client (`frontend/src/lib/api/client.ts`)

The SPA makes every request through `fetchApi`; no other module calls `fetch` for API data.

- **Base URL:** read at request time from `filters.apiBaseUrl` in `frontend/src/lib/stores/filters.svelte.ts`. It starts as `DEFAULT_API_BASE_URL`, which is the build-time `VITE_API_BASE_URL` (trimmed, trailing slashes removed) or `''` when unset. The sidebar's API settings can change it at runtime.
- **URL building:** `<base><endpoint>?<query>`. With an empty base the URL is relative (`/api/...`), so requests go to the page's own origin. `buildQueryParams` skips `undefined`, `null` and `''`, repeats array values (`retailer=A&retailer=B`) and stringifies booleans.
- **Return value:** the parsed envelope, typed as `{data, meta}` (`errors` is still present at runtime but not part of the type).
- **Errors:** every failure throws `ApiErrorResponse` (`status`, `code`, `message`, `meta`):

| Situation | `status` | `code` | `meta` |
|---|---|---|---|
| `fetch` itself fails (server down, CORS, DNS) | `0` | `network_error` (client-only) | — |
| Body is not valid JSON | HTTP status | `bad_response` (client-only) | — |
| Non-2xx with an envelope | HTTP status | `errors[0].code` from the server (§2.3) | envelope `meta` |
| Non-2xx without `errors` | HTTP status | `http_error` | envelope `meta` |

`network_error` and `bad_response` are generated by the client and never sent by the server. Views wrap calls in `AsyncResource` (`frontend/src/lib/utils/async.svelte.ts`), which stores `data`, `meta`, `loading`, `error` and `errorMeta` and ignores responses that a newer request has superseded.

---

## 8. Verification

All Falcon API endpoints are validated by regression test suites:
- `uv run python scripts/verify_falcon_api.py` (in-process TestClient smoke suite)
- `uv run pytest` (`tests/test_api.py` covers the error envelopes and 503 behaviour)

See [TESTING.md](TESTING.md).

### Verification Requirements:
1. **Zero Leaked Types:** Payloads must never leak NaN, Infinity, pandas `NaT`/`NA`, or numpy scalars into JSON.
2. **Deterministic Envelopes:** All endpoints must always return `{ "data", "meta", "errors" }`.
3. **CORS Headers:** `Access-Control-Allow-Origin` must be present on responses (including errors) and preflight requests.
4. **Boundary Isolation:** Handlers and adapters must respect domain boundaries and never import browser presentation code.
