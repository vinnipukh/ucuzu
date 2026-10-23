<script lang="ts">
  import { fetchApi } from '$lib/api/client';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import ProductCard from '$lib/components/ProductCard.svelte';
  import { groupLabel, itemHref } from '$lib/catalog';
  import { catalog, loadGroups } from '$lib/stores/catalog.svelte';
  import { AsyncResource } from '$lib/utils/async.svelte';
  import type { CatalogOffer } from '$lib/types/api';

  const DROPS = [10, 20, 30, 50];
  const PERIODS = [
    { days: 7, label: 'Son 7 gün' },
    { days: 30, label: 'Son 30 gün' }
  ];

  const deals = new AsyncResource<CatalogOffer[]>();
  let group = $state<string | null>(null);
  let minDrop = $state(10);
  let days = $state(30);

  $effect(() => {
    void loadGroups();
  });

  $effect(() => {
    const params = { group, min_drop: minDrop, days, limit: 60 };
    void deals.run(() => fetchApi<CatalogOffer[]>('/api/catalog/deals', params));
  });
</script>

<svelte:head>
  <title>Fiyatı düşenler – ucuzu</title>
</svelte:head>

<div class="head">
  <h1>Fiyatı düşen ürünler</h1>
  <p class="muted">Son fiyat değişikliği bir indirim olan güncel ürünler, en büyük düşüş önce.</p>
</div>

<div class="controls">
  <div class="chips" role="group" aria-label="Kategori">
    <button type="button" class:active={group === null} onclick={() => (group = null)}>Tümü</button>
    {#each catalog.groups as g (g.group)}
      <button type="button" class:active={group === g.group} onclick={() => (group = g.group)}>
        {groupLabel(g.group)}
      </button>
    {/each}
  </div>
  <div class="selects">
    <label>
      <span class="muted">En az düşüş</span>
      <select bind:value={minDrop}>
        {#each DROPS as drop (drop)}<option value={drop}>%{drop}</option>{/each}
      </select>
    </label>
    <label>
      <span class="muted">Dönem</span>
      <select bind:value={days}>
        {#each PERIODS as period (period.days)}<option value={period.days}>{period.label}</option>{/each}
      </select>
    </label>
  </div>
</div>

{#if deals.error}
  <ApiAlert message={deals.error} errorMeta={deals.errorMeta} />
{:else if deals.value && deals.value.length === 0 && !deals.loading}
  <p class="muted empty">Bu filtrelerle fiyatı düşen ürün yok.</p>
{:else}
  <div class="product-grid six" class:loading={deals.loading}>
    {#each deals.value ?? [] as deal (deal.retailer + deal.product_id)}
      <ProductCard
        href={itemHref(deal.item_id!, deal.product_name)}
        name={deal.product_name}
        group={deal.group}
        price={deal.latest_price}
        oldPrice={deal.previous_price}
        dropPercent={deal.drop_percent}
        storeLine={deal.store}
      />
    {/each}
  </div>
{/if}

<style>
  .head h1 {
    margin: 0 0 4px;
    font-size: 1.5rem;
  }
  .head p {
    margin: 0 0 20px;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 20px;
  }
  .chips {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .chips button {
    flex: none;
    padding: 6px 14px;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-card);
    color: var(--color-foreground);
    font-size: 0.85rem;
  }
  .chips button.active {
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
    color: var(--color-accent);
    font-weight: 600;
  }
  .selects {
    display: flex;
    gap: 12px;
  }
  .selects label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
  }
  select {
    height: 36px;
    padding: 0 8px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    background: var(--color-card);
    color: var(--color-foreground);
  }
  .loading {
    opacity: 0.5;
  }
  .empty {
    padding: 40px 0;
    text-align: center;
  }
</style>
