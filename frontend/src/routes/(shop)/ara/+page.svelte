<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { fetchApi } from '$lib/api/client';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import ProductCard from '$lib/components/ProductCard.svelte';
  import { groupLabel, itemHref, searchHref } from '$lib/catalog';
  import { catalog, loadGroups } from '$lib/stores/catalog.svelte';
  import { AsyncResource } from '$lib/utils/async.svelte';
  import type { CatalogSearchItem, CatalogSearchMeta, CatalogSort } from '$lib/types/api';

  const PAGE_SIZE = 24;
  const SORTS: { id: CatalogSort; label: string }[] = [
    { id: 'relevance', label: 'Önerilen' },
    { id: 'price_asc', label: 'En düşük fiyat' },
    { id: 'price_desc', label: 'En yüksek fiyat' },
    { id: 'drop', label: 'En çok düşen' }
  ];

  const results = new AsyncResource<CatalogSearchItem[], CatalogSearchMeta>();

  const q = $derived(page.url.searchParams.get('q') ?? '');
  const group = $derived(page.url.searchParams.get('group'));
  const store = $derived(page.url.searchParams.get('store'));
  const sort = $derived((page.url.searchParams.get('sort') as CatalogSort | null) ?? 'relevance');
  const pageNo = $derived(Math.max(1, Number(page.url.searchParams.get('sayfa')) || 1));
  const total = $derived(results.meta?.total ?? 0);
  const pages = $derived(Math.max(1, Math.ceil(total / PAGE_SIZE)));
  const groupInfo = $derived(catalog.groups.find((g) => g.group === group));

  $effect(() => {
    void loadGroups();
  });

  $effect(() => {
    const params = { q, group, store, sort, limit: PAGE_SIZE, offset: (pageNo - 1) * PAGE_SIZE };
    void results.run(() => fetchApi<CatalogSearchItem[], CatalogSearchMeta>('/api/catalog/search', params));
  });

  function href(changes: Record<string, string | null>): string {
    const params: Record<string, string | null> = { q, group, store, sort: sort === 'relevance' ? null : sort };
    return searchHref({ ...params, ...changes });
  }

  function changeSort(event: Event): void {
    const value = (event.currentTarget as HTMLSelectElement).value;
    void goto(href({ sort: value === 'relevance' ? null : value }));
  }

  const title = $derived(
    q ? `“${q}” için sonuçlar` : store ? store : group ? groupLabel(group) : 'Tüm ürünler'
  );
</script>

<svelte:head>
  <title>{title} – ucuzu</title>
</svelte:head>

<nav class="crumbs" aria-label="Konum">
  <a href="/">Ana sayfa</a>
  {#if group}<span>›</span><a href={searchHref({ group })}>{groupLabel(group)}</a>{/if}
  {#if store}<span>›</span><span>{store}</span>{/if}
</nav>

<div class="layout">
  <aside class="filters" aria-label="Filtreler">
    <h2>Kategoriler</h2>
    <ul>
      <li><a href={href({ group: null, store: null })} class:active={!group}>Tümü</a></li>
      {#each catalog.groups as g (g.group)}
        <li>
          <a href={href({ group: g.group, store: null })} class:active={group === g.group}>{groupLabel(g.group)}</a>
        </li>
      {/each}
    </ul>
    {#if groupInfo && groupInfo.stores.length > 1}
      <h2>Mağazalar</h2>
      <ul class="store-list">
        <li><a href={href({ store: null })} class:active={!store}>Tüm mağazalar</a></li>
        {#each groupInfo.stores as s (s.retailer)}
          <li>
            <a href={href({ store: s.store })} class:active={store === s.store}>
              {s.store} <span class="muted">({s.offer_count.toLocaleString('tr-TR')})</span>
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </aside>

  <section class="results">
    <div class="results-head">
      <div>
        <h1>{title}</h1>
        <p class="muted">
          {#if results.meta}{total.toLocaleString('tr-TR')} ürün{/if}
        </p>
      </div>
      <label class="sort">
        <span class="muted">Sırala</span>
        <select value={sort} onchange={changeSort}>
          {#each SORTS as option (option.id)}<option value={option.id}>{option.label}</option>{/each}
        </select>
      </label>
    </div>

    {#if results.error}
      <ApiAlert message={results.error} errorMeta={results.errorMeta} />
    {:else if results.value && results.value.length === 0 && !results.loading}
      <div class="empty">
        <p><strong>Sonuç bulunamadı.</strong></p>
        <p class="muted">Daha kısa veya farklı bir arama deneyin.</p>
      </div>
    {:else}
      <div class="product-grid" class:loading={results.loading}>
        {#each results.value ?? [] as item (item.id)}
          <ProductCard
            href={itemHref(item.id, item.name)}
            name={item.name}
            group={item.group}
            price={item.min_price}
            priceLabel={item.store_count > 1 ? 'en ucuz' : undefined}
            dropPercent={sort === 'drop' ? item.max_drop_percent : null}
            storeLine={item.store_count > 1 ? `${item.store_count} mağazada · ${item.stores.join(', ')}` : item.store}
          />
        {/each}
      </div>
      {#if pages > 1}
        <nav class="pager" aria-label="Sayfalar">
          {#if pageNo > 1}<a href={href({ sayfa: String(pageNo - 1) })}>‹ Önceki</a>{/if}
          <span class="muted">Sayfa {pageNo} / {pages.toLocaleString('tr-TR')}</span>
          {#if pageNo < pages}<a href={href({ sayfa: String(pageNo + 1) })}>Sonraki ›</a>{/if}
        </nav>
      {/if}
    {/if}
  </section>
</div>

<style>
  .crumbs {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    color: var(--color-muted-foreground);
    font-size: 0.82rem;
  }
  .crumbs a {
    color: inherit;
    text-decoration: none;
  }
  .crumbs a:hover {
    color: var(--color-accent);
  }
  .layout {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 28px;
    align-items: start;
  }
  .filters {
    position: sticky;
    top: 130px;
    max-height: calc(100vh - 150px);
    overflow: auto;
  }
  .filters h2 {
    margin: 0 0 8px;
    font-size: 0.9rem;
  }
  .filters ul {
    margin: 0 0 22px;
    padding: 0;
    list-style: none;
  }
  .filters a {
    display: block;
    padding: 5px 10px;
    border-radius: 6px;
    color: var(--color-foreground);
    font-size: 0.87rem;
    text-decoration: none;
  }
  .filters a:hover {
    background: var(--color-muted);
  }
  .filters a.active {
    background: var(--color-accent-soft);
    color: var(--color-accent);
    font-weight: 600;
  }
  .results-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }
  .results-head h1 {
    margin: 0;
    font-size: 1.35rem;
  }
  .results-head p {
    margin: 2px 0 0;
    font-size: 0.85rem;
  }
  .sort {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
  }
  .sort select {
    height: 38px;
    padding: 0 10px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    background: var(--color-card);
    color: var(--color-foreground);
  }
  .loading {
    opacity: 0.5;
    transition: opacity 0.2s;
  }
  .empty {
    padding: 48px 0;
    text-align: center;
  }
  .pager {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 18px;
    margin-top: 28px;
  }
  .pager a {
    padding: 8px 16px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    background: var(--color-card);
    color: var(--color-foreground);
    text-decoration: none;
  }
  .pager a:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }
  @media (max-width: 860px) {
    .layout {
      grid-template-columns: 1fr;
    }
    .filters {
      position: static;
      max-height: none;
    }
    .filters ul {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      margin-bottom: 12px;
    }
    .filters li {
      flex: none;
    }
    .filters h2 {
      display: none;
    }
  }
</style>
