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
