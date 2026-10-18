/**
 * Price alarms, kept in this browser's localStorage (the API is read-only).
 * An alarm fires when an item's lowest current price is at or below its target.
 */

/** One price alarm on a catalog item. */
export interface PriceAlarm {
  key: string;
  name: string;
  target: number;
  priceWhenSet: number | null;
  createdAt: string;
}

const STORAGE_KEY = 'price-alarms';

function load(): PriceAlarm[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(alarms.list));
  } catch {
    // Storage blocked or full: alarms live for this session only.
  }
}

/** Reactive alarm list, loaded once from localStorage. */
export const alarms = $state({ list: typeof localStorage === 'undefined' ? [] : load() });

/** The alarm for `key`, if any. */
export function alarmFor(key: string): PriceAlarm | undefined {
  return alarms.list.find((alarm) => alarm.key === key);
}

/** Create or replace the alarm for an item. */
export function setAlarm(key: string, name: string, target: number, priceWhenSet: number | null): void {
  const alarm: PriceAlarm = { key, name, target, priceWhenSet, createdAt: new Date().toISOString() };
  alarms.list = [alarm, ...alarms.list.filter((a) => a.key !== key)];
  save();
}

/** Delete the alarm for an item. */
export function removeAlarm(key: string): void {
  alarms.list = alarms.list.filter((a) => a.key !== key);
  save();
}
