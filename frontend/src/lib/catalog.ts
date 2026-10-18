/**
 * Shared helpers for the price-comparison pages: Turkish group labels, item
 * links and price formatting.
 */

/** Turkish display names for catalog groups (retailer label prefixes). */
const GROUP_LABELS: Record<string, string> = {
  Markets: 'Market',
  Cosmetics: 'Kozmetik',
  HomeGoods: 'Ev & Yaşam',
  ClothingStores: 'Giyim & Moda',
  Communication: 'Elektronik',
  ConstructionSuppliesMarkets: 'Yapı Market',
  Technology: 'Teknoloji',
  Recreation: 'Kitap & Hobi',
  'Alcohol Tobacco': 'Alkol & Sigara',
  Restaurants: 'Restoran & Seyahat',
  Transport: 'Ulaşım',
  'Personal Care': 'Kişisel Bakım',
  Health: 'Sağlık',
  EpeyKatfg: 'Epey Katalog'
};

/** Display name for a catalog group; unknown groups show as-is. */
export function groupLabel(group: string): string {
  return GROUP_LABELS[group] ?? group;
}

/** Link to an item's comparison page. */
export function itemHref(key: string): string {
  return `/urun/${encodeURIComponent(key)}`;
}

/** Link to the search page with the given parameters (empty values dropped). */
export function searchHref(params: Record<string, string | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value) query.set(key, value);
  const text = query.toString();
  return text ? `/ara?${text}` : '/ara';
}

/** Price as `1.234,50 TL`; whole numbers drop the decimals. */
export function formatTL(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const whole = Number.isInteger(value);
  return `${value.toLocaleString('tr-TR', {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2
  })} TL`;
}

/** `2026-10-17` -> `17 Eki 2026`. */
export function formatDayTR(value: string | null | undefined): string {
  if (!value) return '-';
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
}

/** Two-letter monogram used as the product image placeholder. */
export function monogram(name: string): string {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? '?') + (words[1]?.[0] ?? '')).toLocaleUpperCase('tr-TR');
}

/** Stable hue (0-359) for a string, for placeholder tints. */
export function hueOf(text: string): number {
  let hash = 0;
  for (const char of text) hash = (hash * 31 + char.codePointAt(0)!) | 0;
  return Math.abs(hash) % 360;
}
