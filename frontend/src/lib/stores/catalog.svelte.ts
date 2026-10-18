import { fetchApi } from '$lib/api/client';
import type { CatalogGroup } from '$lib/types/api';

/** Catalog groups shared by the header menu and the home page; loaded once. */
export const catalog = $state({
  groups: [] as CatalogGroup[],
  loading: false,
  error: null as string | null
});

let pending: Promise<void> | null = null;

/** Load `/api/catalog/groups` once; later calls reuse the first request. */
export function loadGroups(): Promise<void> {
  if (pending) return pending;
  catalog.loading = true;
  pending = fetchApi<CatalogGroup[]>('/api/catalog/groups')
    .then((response) => {
      catalog.groups = response.data;
      catalog.error = null;
    })
    .catch((err) => {
      catalog.error = err instanceof Error ? err.message : String(err);
      pending = null;
    })
    .finally(() => {
      catalog.loading = false;
    });
  return pending;
}
