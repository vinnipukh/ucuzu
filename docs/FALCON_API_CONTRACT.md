# Falcon REST API Contract & Specification

**Target Frontend:** Svelte 5 / SvelteKit SPA (`frontend/`)  
**API Backend:** Falcon WSGI application (`inflation_dashboard/api/falcon_app.py`)  
**Specification Version:** 2.1.0  
**Last Updated:** 2026-10-17  
**Status:** Authoritative. [API.md](API.md) is a summary; this file wins on any difference.

---

## 1. Transport

- **Protocol:** HTTP/1.1 through a WSGI server (Granian, Gunicorn or Waitress; see [CONFIGURATION.md](CONFIGURATION.md)). Only `GET` routes exist.
- **Base URL:** the SPA calls same-origin `/api/...` unless `VITE_API_BASE_URL` was set at build time.
- **Content-Type:** `application/json`, UTF-8.
- **Serialization:** `orjson`. `NaN`, `Infinity`, `NaT` and pandas/numpy scalars are converted to JSON-native values (`null` for missing) before encoding.
- **CORS:** `falcon.CORSMiddleware` with `FALCON_CORS_ORIGINS` (default `*`). It adds `Access-Control-Allow-Origin` to every response, including errors. Preflight `OPTIONS` returns `200` with `Access-Control-Allow-Methods: GET`, `Access-Control-Allow-Headers: *` and `Access-Control-Max-Age: 86400`. No headers are exposed (`ETag` is not readable cross-origin from JavaScript, but the browser cache still uses it).
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
| 404 | `not_found` | Unknown route, or `/api/product` found no product | `Product not found: <key>` for products; Falcon's description or title for routes |
| 405 | `method_not_allowed` | A method other than `GET`/`OPTIONS` on a known route (the `Allow` header lists `GET`) | Falcon's description or title |
| other 4xx/5xx | `http_error` | Any other `falcon.HTTPError` raised by Falcon | Falcon's description or title |
| 500 | `server_error` | Any unhandled exception | Always the fixed string `Internal server error`; the traceback is logged server-side (logger `inflation_dashboard.api`), never sent |
| 503 | `database_unavailable` | The configured database file is missing or 0 bytes (every endpoint except `/api/health` and `/api/epeykatfg/monthly-inflation`) | `Database not found; run scripts/build_database.py` |

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
    "retailers": ["Alcohol Tobacco / AlkolFiyatlari", "…", "Markets / Gurmar", "…", "Technology", "…"],
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
        "source_file": "raw/01_Food/Gurmar/gurmar_prices_2026-10-17.csv"
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

Rows are ordered by retailer, product name, date. `source_file` is relative to `data/` (`<file>.json#YYYY-MM-DD` for JSON-sourced retailers).

**Product mode**

```json
{
  "data": {
    "history": [
      {"date": "2026-10-16T00:00:00", "price": 1349.9, "category": "Uncategorized", "source_file": "raw/01_Food/Gurmar/gurmar_prices_2026-10-16.csv"},
      {"date": "2026-10-17T00:00:00", "price": 1349.9, "category": "Uncategorized", "source_file": "raw/01_Food/Gurmar/gurmar_prices_2026-10-17.csv"}
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

Lookup: the key is matched against `product_id`, then against `product_name`. With `retailer`, only that retailer is searched; without it, the match with the most observations wins. No match (or a database error during lookup) returns 404 `not_found` with message `Product not found: <key>` and `meta` `{product_id, product_name, retailer}` echoing the request.

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

---

## 5. Caching and compression

Applies to the successful (200) responses of every endpoint except `/api/health`. Error responses are never cached.

- **Server cache:** the serialized body is cached in-process per endpoint and raw query string for 300 seconds (up to 512 entries and 1 GiB per worker). Identical requests are served from it without recomputation.
- **ETag:** a strong ETag (quoted MD5 of the body bytes) on every cacheable response. The gzip and plain variants have different ETags.
- **Conditional requests:** `If-None-Match` matching the current ETag (or `*`) returns `304 Not Modified` with the same `ETag`, `Cache-Control` and `Vary` headers and no body.
- **Cache-Control:** `public, max-age=300`.
- **Compression:** bodies of at least 1 KB (1024 bytes) also get a gzip variant. It is sent with `Content-Encoding: gzip` when `Accept-Encoding` allows gzip (q > 0). Whenever a gzip variant exists, the response carries `Vary: Accept-Encoding`, whichever variant was sent.

---

## 6. TypeScript Interfaces for the Svelte Frontend

The following TypeScript definitions should be placed in `src/lib/types/api.ts` in the Svelte application:

```typescript
/**
 * Standard API Response Envelope.
 */
export interface ApiResponse<T, M = Record<string, unknown>> {
  data: T;
  meta: M;
  errors: ApiError[];
}

/**
 * Standard API Error Detail.
 */
export interface ApiError {
  code: string;
  message: string;
  meta?: Record<string, unknown>;
}

/**
 * Error Envelope (data is null on failure).
 */
export interface ApiErrorEnvelope {
  data: null;
  meta: Record<string, unknown>;
  errors: ApiError[];
}

// ── Common Filter Parameters ──────────────────────────────────────────────────

export interface CommonFilterParams {
  retailer?: string | string[];
  start_date?: string; // YYYY-MM-DD
  end_date?: string;   // YYYY-MM-DD
  max_files?: number;
  all_history?: boolean;
}

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

export interface HealthData {
  status: "ok" | string;
}

export interface HealthMeta {
  service: string;
}

export type HealthResponse = ApiResponse<HealthData, HealthMeta>;

// ── 2. Inventory ──────────────────────────────────────────────────────────────

export interface InventoryData {
  retailers: string[];
  min_date: string | null; // ISO datetime/date
  max_date: string | null; // ISO datetime/date
}

export interface InventoryMeta {
  file_count: number;
  inventory_file_count: number;
}

export type InventoryResponse = ApiResponse<InventoryData, InventoryMeta>;

// ── 3. History ────────────────────────────────────────────────────────────────

export interface HistoryRecord {
  date: string; // ISO datetime: "2026-09-02T00:00:00"
  retailer: string;
  product_id: string | null;
  product_name: string;
  category: string | null;
  price: number | null;
  source_file: string;
}

export interface ProductHistoryPoint {
  date: string;
  price: number | null;
  category: string | null;
  source_file: string;
}

export interface ProductSummary {
  latest_price: number | null;
  cheapest_price: number | null;
  cheapest_date: string | null;
  change_since_first_pct: number;
}

export interface GeneralHistoryData {
  history: HistoryRecord[];
}

export interface ProductHistoryData {
  history: ProductHistoryPoint[];
  summary: ProductSummary;
}

export interface HistoryMeta extends CommonFilterMeta {
  product_name?: string;
  product_retailer?: string;
}

export type HistoryResponse = ApiResponse<GeneralHistoryData | ProductHistoryData, HistoryMeta>;

// ── 4. Retailer Averages ──────────────────────────────────────────────────────

export interface RetailerAverageRecord {
  date: string;
  retailer: string;
  price: number | null;
}

export interface RetailerAveragesData {
  records: RetailerAverageRecord[];
  retailer_averages: RetailerAverageRecord[];
}

export interface RetailerAveragesMeta extends CommonFilterMeta {
  aggregation: "Average" | "Median";
}

export type RetailerAveragesResponse = ApiResponse<RetailerAveragesData, RetailerAveragesMeta>;

// ── 5. Movers ─────────────────────────────────────────────────────────────────

export interface MoverDropRecord {
  retailer: string;
  product_name: string;
  latest_price: number | null;
  max_price: number | null;
  savings_vs_peak: number | null;
  drop_from_peak_pct: number | null;
  last_seen: string | null;
}

export interface MoverGainRecord {
  retailer: string;
  product_name: string;
  first_price: number | null;
  latest_price: number | null;
  change_since_first_pct: number | null;
  first_seen: string | null;
  last_seen: string | null;
}

export interface MoversData {
  biggest_drops: MoverDropRecord[];
  biggest_gains: MoverGainRecord[];
}

export interface MoversMeta extends CommonFilterMeta {
  scope_retailer: string;
  limit: number;
  eligible_product_count: number;
}

export type MoversResponse = ApiResponse<MoversData, MoversMeta>;

// ── 6. Coverage ───────────────────────────────────────────────────────────────

export interface CoverageSummary {
  retailer_count: number;
  product_count: number;
  observation_count: number;
  date_range: string;
  skipped_file_count: number;
}

export interface CoverageOverTimeRecord {
  date: string;
  retailer: string;
  tracked_products: number;
}

export interface CategoryCoverageRecord {
  retailer: string;
  category: string;
  products: number;
}

export interface SkippedFileDiagnostic {
  file: string;
  reason: string;
}

export interface CoverageData {
  summary: CoverageSummary;
  coverage_over_time: CoverageOverTimeRecord[];
  category_coverage: CategoryCoverageRecord[];
  skipped_files: SkippedFileDiagnostic[];
}

export interface CoverageMeta extends CommonFilterMeta {
  category_limit: number;
}

export type CoverageResponse = ApiResponse<CoverageData, CoverageMeta>;

// ── Product search, detail and monthly inflation ──────────────────────────────

export interface ProductSearchResult {
  product_id: string;
  retailer: string;
  product_name: string | null;
  category: string | null;
  first_date: string | null;
  last_date: string | null;
  latest_price: number | null;
  min_price: number | null;
  max_price: number | null;
  observations_count: number;
}

export interface ProductSearchMeta {
  query: string;
  retailer: string | null;
  category: string | null;
  limit: number;
  count: number;
}

export type ProductSearchResponse = ApiResponse<ProductSearchResult[], ProductSearchMeta>;

export interface ProductHistoryRecord {
  date: string;
  price: number;
  category: string | null;
  source_file: string;
}

export interface ProductDetailData extends ProductSearchResult {
  price_history: Record<string, number>;
  history: ProductHistoryRecord[];
  summary: {
    latest_price: number | null;
    cheapest_price: number | null;
    cheapest_date: string | null;
    change_since_first_pct: number;
  };
}

export interface ProductDetailMeta {
  product_id: string;
  retailer: string;
  observations_count: number;
}

export type ProductDetailResponse = ApiResponse<ProductDetailData, ProductDetailMeta>;

export interface MonthlyInflationRecord {
  month: string;
  prev_month: string;
  n_matched: number;
  avg_inflation: number | null;
  basic_index: number | null;
  median_inflation_nonzero: number | null;
  tuik_weighted: number | null;
  covered_weight: number | null;
  groups: string;
  [key: string]: string | number | null;
}

export interface MonthlyInflationMeta {
  count: number;
  columns: string[];
  source: string;
  notes: string;
}

export type MonthlyInflationResponse = ApiResponse<MonthlyInflationRecord[], MonthlyInflationMeta>;
```

---

## 7. Svelte Frontend Integration Patterns

### 7.1 Recommended API Client Helper (`src/lib/api/client.ts`)

```typescript
import type { ApiResponse, CommonFilterParams } from '$lib/types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiErrorResponse extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public meta?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiErrorResponse';
  }
}

/**
 * Serializes CommonFilterParams into URLSearchParams handling array fields.
 */
export function buildQueryParams(params: Record<string, any>): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        query.append(key, String(item));
      }
    } else {
      query.set(key, String(value));
    }
  }
  return query;
}

/**
 * Universal type-safe fetcher for Falcon API endpoints.
 */
export async function fetchApi<T, M = Record<string, unknown>>(
  endpoint: string,
  params?: Record<string, any>,
  fetchFn: typeof fetch = fetch
): Promise<ApiResponse<T, M>> {
  const queryString = params ? `?${buildQueryParams(params).toString()}` : '';
  const url = `${API_BASE_URL}${endpoint}${queryString}`;

  const res = await fetchFn(url, {
    headers: {
      Accept: 'application/json',
    },
  });

  const payload = await res.json();

  if (!res.ok) {
    const error = payload.errors?.[0] || {
      code: 'http_error',
      message: `Request failed with status ${res.status}`,
    };
    throw new ApiErrorResponse(res.status, error.code, error.message, error.meta || payload.meta);
  }

  return payload as ApiResponse<T, M>;
}
```

### 7.2 Svelte 5 Rune State Management Example

```svelte
<script lang="ts">
  import { fetchApi } from '$lib/api/client';
  import type { InventoryData, InventoryMeta, RetailerAverageRecord } from '$lib/types/api';

  let inventory = $state<InventoryData | null>(null);
  let selectedRetailers = $state<string[]>([]);
  let averages = $state<RetailerAverageRecord[]>([]);
  let loading = $state(false);
  let errorMessage = $state<string | null>(null);

  // Load initial inventory
  async function loadInventory() {
    try {
      loading = true;
      const res = await fetchApi<InventoryData, InventoryMeta>('/api/inventory');
      inventory = res.data;
      selectedRetailers = res.data.retailers.slice(0, 3);
      await loadAverages();
    } catch (err: any) {
      errorMessage = err.message;
    } finally {
      loading = false;
    }
  }

  // Reload trend averages when filters change
  async function loadAverages() {
    try {
      loading = true;
      errorMessage = null;
      const res = await fetchApi<{ records: RetailerAverageRecord[] }>('/api/retailer-averages', {
        retailer: selectedRetailers,
        aggregation: 'Average'
      });
      averages = res.data.records;
    } catch (err: any) {
      errorMessage = err.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    loadInventory();
  });
</script>

{#if loading}
  <div class="spinner">Loading inflation statistics...</div>
{:else if errorMessage}
  <div class="alert alert-error">{errorMessage}</div>
{:else}
  <div class="dashboard-grid">
    <div class="metric-card">
      <h3>Monitored Retailers</h3>
      <p>{selectedRetailers.join(', ')}</p>
    </div>
    <div class="metric-card">
      <h3>Data Points</h3>
      <p>{averages.length} trend records</p>
    </div>
  </div>
{/if}
```

---

## 8. Verification & Compliance Checklist

All Falcon API endpoints are validated by regression test suites:
- `python scripts/verify_falcon_api.py` (Falcon API in-process TestClient smoke suite)

### Verification Requirements:
1. **Zero Leaked Types:** Payloads must never leak NaN, Infinity, pandas `NaT`/`NA`, or numpy scalars into JSON.
2. **Deterministic Envelopes:** All endpoints must always return `{ "data", "meta", "errors" }`.
3. **CORS Headers:** `Access-Control-Allow-Origin` must be present on responses (including errors) and preflight requests.
4. **Boundary Isolation:** Handlers and adapters must respect domain boundaries and never import browser presentation code.
