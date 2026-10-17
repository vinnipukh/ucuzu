import type { CommonFilterParams } from '$lib/types/api';

const ENV_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined;

/**
 * Build-time default API origin (VITE_API_BASE_URL, trailing slashes removed).
 * Empty when unset or blank, meaning same-origin `/api/...` requests (served by
 * the Vite dev proxy or a reverse proxy). The user can override it at runtime in
 * the sidebar.
 */
export const DEFAULT_API_BASE_URL: string = ENV_BASE?.trim() ? ENV_BASE.trim().replace(/\/+$/, '') : '';

// Retailers load one category at a time (per owner request): the first visit opens on
// Markets, later visits on the last category used. All files in the date range are loaded.
/** Category loaded on a first visit (before any choice is remembered). */
export const DEFAULT_CATEGORY = 'Markets';
const CATEGORY_STORAGE_KEY = 'inflation-dashboard:category';
const DEFAULT_ALL_HISTORY = true;

/** Category of a retailer label: the group before " / " (e.g. "Markets / Gurmar" -> "Markets"). */
export function retailerCategory(retailer: string): string {
  const separator = retailer.indexOf(' / ');
  return separator === -1 ? retailer : retailer.slice(0, separator);
}

function readStoredCategory(): string | null {
  try {
    return localStorage.getItem(CATEGORY_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeCategory(category: string): void {
  try {
    localStorage.setItem(CATEGORY_STORAGE_KEY, category);
  } catch {
    // Storage unavailable (private mode, blocked site data): the choice just isn't remembered.
  }
}

/**
 * Global dashboard filter state (Svelte 5 runes, object form so components can
 * bind/mutate individual properties): retailer selection, date window, file cap,
 * all-history mode and the runtime API origin.
 */
export const filters = $state({
  /** Live API origin used by every request. */
  apiBaseUrl: DEFAULT_API_BASE_URL,
  retailerOptions: [] as string[],
  /** Sorted distinct retailer categories present in the inventory. */
  categoryOptions: [] as string[],
  /** Category whose retailers are loaded; null once the selection is edited by hand. */
  category: null as string | null,
  inventoryMinDate: null as string | null,
  inventoryMaxDate: null as string | null,
  inventoryFileCount: null as number | null,
  selectedRetailers: [] as string[],
  startDate: null as string | null,
  endDate: null as string | null,
  maxFiles: 45,
  allHistory: DEFAULT_ALL_HISTORY,
  /** True once inventory has been loaded successfully for the current API. */
  inventoryReady: false
});

/** Clear inventory-derived state and restore defaults (used when inventory loading fails). */
export function resetFilters(): void {
  filters.retailerOptions.length = 0;
  filters.categoryOptions.length = 0;
  filters.category = null;
  filters.inventoryMinDate = null;
  filters.inventoryMaxDate = null;
  filters.inventoryFileCount = null;
  filters.selectedRetailers.length = 0;
  filters.startDate = null;
  filters.endDate = null;
  filters.maxFiles = 45;
  filters.allHistory = DEFAULT_ALL_HISTORY;
  filters.inventoryReady = false;
}

/**
 * Populate options from `/api/inventory`, select the initial category
 * (remembered, else `DEFAULT_CATEGORY`, else the first) and set the last 60 days as the date range.
 */
export function initInventory(retailers: string[], minDate: string | null, maxDate: string | null): void {
  filters.retailerOptions.length = 0;
  filters.retailerOptions.push(...retailers);
  filters.inventoryMinDate = minDate;
  filters.inventoryMaxDate = maxDate;

  filters.categoryOptions.length = 0;
  filters.categoryOptions.push(...[...new Set(retailers.map(retailerCategory))].sort((a, b) => a.localeCompare(b)));

  const remembered = readStoredCategory();
  const initial = [remembered, DEFAULT_CATEGORY, filters.categoryOptions[0]].find(
    (candidate): candidate is string => !!candidate && filters.categoryOptions.includes(candidate)
  );
  if (initial) {
    selectCategory(initial);
  } else {
    filters.category = null;
    filters.selectedRetailers.length = 0;
  }

  const min = parseDate(minDate);
  const max = parseDate(maxDate);
  if (min && max) {
    const defaultStart = new Date(max.getTime() - 60 * 24 * 60 * 60 * 1000);
    const start = defaultStart < min ? min : defaultStart;
    filters.startDate = toInputDate(start);
    filters.endDate = toInputDate(max);
  } else {
    filters.startDate = null;
    filters.endDate = null;
  }
  filters.inventoryReady = true;
}

/** Load every retailer of one category and remember the choice for the next visit. */
export function selectCategory(category: string): void {
  filters.category = category;
  filters.selectedRetailers.length = 0;
  filters.selectedRetailers.push(...filters.retailerOptions.filter((name) => retailerCategory(name) === category));
  storeCategory(category);
}

/** Hand-edited retailer selection; the category label is kept only while it still matches exactly. */
export function setSelectedRetailers(next: string[]): void {
  filters.selectedRetailers.length = 0;
  filters.selectedRetailers.push(...next);
  if (filters.category) {
    const members = filters.retailerOptions.filter((name) => retailerCategory(name) === filters.category);
    const matches = members.length === next.length && members.every((name) => next.includes(name));
    if (!matches) filters.category = null;
  }
}

/** Build the common filter params reactively from the current state. Currently unused: views call `buildQueryMap`. */
export function buildCommonParams(): CommonFilterParams {
  return {
    retailer: [...filters.selectedRetailers],
    start_date: filters.startDate ?? undefined,
    end_date: filters.endDate ?? undefined,
    max_files: filters.allHistory ? 0 : filters.maxFiles,
    all_history: filters.allHistory
  };
}

/** Serialized param map for the API (empty strings are dropped by the client). */
export function buildQueryMap(): Record<string, unknown> {
  return {
    retailer: [...filters.selectedRetailers],
    start_date: filters.startDate ?? '',
    end_date: filters.endDate ?? '',
    max_files: filters.allHistory ? 0 : filters.maxFiles,
    all_history: filters.allHistory
  };
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;
  return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
}

function toInputDate(date: Date): string {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
