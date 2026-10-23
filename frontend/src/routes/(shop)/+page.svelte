<script lang="ts">
  import { fetchApi } from '$lib/api/client';
  import Icon from '$lib/components/Icon.svelte';
  import ProductCard from '$lib/components/ProductCard.svelte';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import { formatDayTR, groupLabel, itemHref, searchHref } from '$lib/catalog';
  import { catalog, loadGroups } from '$lib/stores/catalog.svelte';
  import type { CatalogGroup, CatalogOffer, CatalogSearchItem } from '$lib/types/api';

  const SHOWCASE_GROUPS = 4;

  let deals = $state<CatalogOffer[]>([]);
  let dealsError = $state<string | null>(null);
  let popular = $state<Record<string, CatalogSearchItem[]>>({});

  const showcase = $derived(catalog.groups.slice(0, SHOWCASE_GROUPS));
  const storeCount = $derived(catalog.groups.reduce((sum, g) => sum + g.stores.length, 0));
  const offerCount = $derived(catalog.groups.reduce((sum, g) => sum + g.offer_count, 0));
  const lastDate = $derived(catalog.groups.map((g) => g.last_date ?? '').sort().at(-1) ?? null);
  const topStores = $derived(
    catalog.groups
      .flatMap((g) => g.stores.map((s) => ({ ...s, group: g.group })))
      .sort((a, b) => b.offer_count - a.offer_count)
      .slice(0, 18)
  );

  $effect(() => {
    fetchApi<CatalogOffer[]>('/api/catalog/deals', { limit: 12, min_drop: 10 })
      .then((r) => (deals = r.data))
      .catch((err) => (dealsError = err instanceof Error ? err.message : String(err)));
    void loadGroups();
  });

  async function loadPopular(group: CatalogGroup): Promise<void> {
    const response = await fetchApi<CatalogSearchItem[]>('/api/catalog/search', { group: group.group, limit: 6 });
    popular[group.group] = response.data;
  }

  $effect(() => {
    for (const group of showcase) if (!popular[group.group]) void loadPopular(group).catch(() => {});
  });
</script>

<svelte:head>
  <title>ucuzu – En ucuz fiyatı bul</title>
</svelte:head>

<section class="tiles">
  <a class="tile blue" href="/firsatlar">
    <Icon name="trend" size={26} />
    <span>Fiyatı Düşenler</span>
  </a>
  <a class="tile green" href={searchHref({ sort: 'drop' })}>
    <Icon name="tag" size={26} />
    <span>En Çok İndirim</span>
  </a>
  <a class="tile purple" href="/alarmlar">
    <Icon name="bell" size={26} />
    <span>Fiyat Alarmı</span>
  </a>
</section>

<section class="hero">
  <div>
    <h1>Aynı ürün, farklı mağaza, farklı fiyat.</h1>
    <p class="muted">
      {#if catalog.groups.length}
        {storeCount} mağazada {offerCount.toLocaleString('tr-TR')} güncel fiyatı karşılaştır. Son güncelleme:
        {formatDayTR(lastDate)}.
      {:else}
        Mağaza fiyatlarını karşılaştır, fiyat geçmişini gör, düşüşleri yakala.
      {/if}
    </p>
  </div>
</section>

{#if catalog.error}
  <ApiAlert message={catalog.error} />
{/if}

<section class="block">
  <div class="section-head">
    <h2>Fiyatı düşen ürünler</h2>
    <a href="/firsatlar">Tümünü gör</a>
  </div>
  {#if dealsError}
    <p class="muted">{dealsError}</p>
  {:else}
    <div class="product-grid six">
      {#each deals as deal (deal.retailer + deal.product_id)}
        <ProductCard
          href={itemHref(deal.item_id!, deal.product_name)}
          name={deal.product_name}
          group={deal.group}
          price={deal.latest_price}
          oldPrice={deal.previous_price}
          dropPercent={deal.drop_percent}
          storeLine={deal.store}
        />
      {:else}
        {#each Array(6) as _, i (i)}<div class="skeleton"></div>{/each}
      {/each}
    </div>
  {/if}
</section>

{#each showcase as group (group.group)}
  <section class="block">
    <div class="section-head">
      <h2>Popüler {groupLabel(group.group)} ürünleri</h2>
      <a href={searchHref({ group: group.group })}>Tümünü gör</a>
    </div>
    <div class="product-grid six">
      {#each popular[group.group] ?? [] as item (item.id)}
        <ProductCard
          href={itemHref(item.id, item.name)}
          name={item.name}
          group={item.group}
          price={item.min_price}
          priceLabel={item.store_count > 1 ? 'en ucuz' : undefined}
          storeLine={item.store_count > 1 ? `${item.store_count} mağazada` : item.store}
        />
      {:else}
        {#each Array(6) as _, i (i)}<div class="skeleton"></div>{/each}
      {/each}
    </div>
  </section>
{/each}

{#if topStores.length}
  <section class="block">
    <div class="section-head"><h2>Popüler mağazalar</h2></div>
    <div class="stores">
      {#each topStores as store (store.retailer)}
        <a href={searchHref({ group: store.group, store: store.store })}>
          <strong>{store.store}</strong>
          <span class="muted">{groupLabel(store.group)} · {store.offer_count.toLocaleString('tr-TR')} ürün</span>
        </a>
      {/each}
    </div>
  </section>
{/if}

<style>
  .tiles {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  .tile {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    height: 52px;
    border-radius: var(--radius-control);
    font-weight: 600;
    text-decoration: none;
  }
  .tile.blue {
    background: #e8f1fd;
    color: #1458b8;
  }
  .tile.green {
    background: #e7f6ee;
    color: #0b7a43;
  }
  .tile.purple {
    background: #efecfd;
    color: #4f3cc9;
  }
  :global(.dark) .tile {
    background: var(--color-muted);
    color: var(--color-foreground);
  }
  .tile:hover {
    filter: brightness(0.97);
  }
  .hero {
    margin: 28px 0 32px;
  }
  .hero h1 {
    margin: 0 0 6px;
    font-size: clamp(1.4rem, 3vw, 2rem);
  }
  .hero p {
    margin: 0;
  }
  .block {
    margin-bottom: 40px;
  }
  .skeleton {
    height: 270px;
    border-radius: var(--radius-panel);
    background: var(--color-muted);
  }
  .stores {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 10px;
  }
  .stores a {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 12px 14px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    background: var(--color-card);
    color: var(--color-foreground);
    font-size: 0.85rem;
    text-decoration: none;
  }
  .stores a:hover {
    border-color: var(--color-accent);
  }
  @media (max-width: 640px) {
    .tiles {
      grid-template-columns: 1fr;
      gap: 8px;
    }
  }
</style>
