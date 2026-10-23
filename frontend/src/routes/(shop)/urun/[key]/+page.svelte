<script lang="ts">
  import { page } from '$app/state';
  import { fetchApi } from '$lib/api/client';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import Chart from '$lib/components/Chart.svelte';
  import Icon from '$lib/components/Icon.svelte';
  import ProductCard from '$lib/components/ProductCard.svelte';
  import Spinner from '$lib/components/Spinner.svelte';
  import { formatDayTR, formatTL, groupLabel, hueOf, itemHref, itemIdFromParam, monogram, searchHref } from '$lib/catalog';
  import { alarmFor, removeAlarm, setAlarm } from '$lib/stores/alarms.svelte';
  import { AsyncResource } from '$lib/utils/async.svelte';
  import { baseChartOption, getChartTheme } from '$lib/utils/chartTheme.svelte';
  import type { CatalogItem, CatalogOffer, CatalogSearchItem } from '$lib/types/api';

  type Range = 30 | 90 | 0;
  const MAX_CHART_SERIES = 6;

  const item = new AsyncResource<CatalogItem>();
  let similar = $state<CatalogSearchItem[]>([]);
  let sizes = $state<CatalogSearchItem[]>([]);
  let range = $state<Range>(90);
  let alarmFormOpen = $state(false);
  let target = $state<number | null>(null);

  // The route segment is `<slug>,<id>`; only the ID matters.
  const id = $derived(itemIdFromParam(page.params.key ?? ''));
  const data = $derived(item.value);
  const current = $derived(data?.offers.filter((o) => o.is_current) ?? []);
  const stale = $derived(data?.offers.filter((o) => !o.is_current) ?? []);
  const best = $derived(current[0] ?? data?.offers[0]);
  const alarm = $derived(id === null ? undefined : alarmFor(id));
  const hue = $derived(hueOf(data?.name ?? String(id)));

  $effect(() => {
    const itemId = id;
    alarmFormOpen = false;
    similar = [];
    sizes = [];
    void item.run(() => fetchApi<CatalogItem>('/api/catalog/item', { id: itemId ?? '' }));
  });

  // "Similar" = same first two words, same group.
  $effect(() => {
    if (!data) return;
    const words = data.name.split(/\s+/).slice(0, 2).join(' ');
    fetchApi<CatalogSearchItem[]>('/api/catalog/search', { q: words, group: data.group, limit: 7 })
      .then((r) => (similar = r.data.filter((s) => s.id !== data.id && s.family_id !== data.family_id).slice(0, 6)))
      .catch(() => (similar = []));
  });

  // Other sizes of the same product (its family).
  $effect(() => {
    if (!data?.family_id) return;
    fetchApi<CatalogSearchItem[]>('/api/catalog/search', { family: data.family_id, sort: 'price_asc', limit: 24 })
      .then((r) => (sizes = r.data.filter((s) => s.id !== data.id)))
      .catch(() => (sizes = []));
  });

  function openAlarmForm(): void {
    const price = data?.summary.min_price;
    target = alarm?.target ?? (price ? Math.floor(price * 0.95 * 100) / 100 : null);
    alarmFormOpen = true;
  }

  function saveAlarm(event: SubmitEvent): void {
    event.preventDefault();
    if (!data || !target || target <= 0) return;
    setAlarm(data.id, data.name, target, data.summary.min_price);
    alarmFormOpen = false;
  }

  // A store's offers often share the item's name (e.g. every repair service for
  // one phone); the product id is then what tells them apart.
  function offerLabel(offer: CatalogOffer): string {
    return offer.product_name === data?.name ? offer.product_id : offer.product_name;
  }

  function changeLabel(offer: CatalogOffer): string | null {
    if (!offer.previous_price || offer.latest_price === null || offer.previous_price === offer.latest_price) return null;
    const pct = ((offer.latest_price - offer.previous_price) / offer.previous_price) * 100;
    return `${pct < 0 ? '↓' : '↑'} %${Math.abs(pct).toLocaleString('tr-TR', { maximumFractionDigits: 1 })}`;
  }

  const chartOption = $derived.by(() => {
    const theme = getChartTheme();
    const offers = (current.length ? current : (data?.offers ?? [])).slice(0, MAX_CHART_SERIES);
    const newest = offers.flatMap((o) => o.history ?? []).reduce((m, [d]) => (d > m ? d : m), '');
    let from = '';
    if (range && newest) {
      const date = new Date(`${newest}T00:00:00Z`);
      date.setUTCDate(date.getUTCDate() - range);
      from = date.toISOString().slice(0, 10);
    }
    const base = baseChartOption(theme);
    return {
      ...base,
      color: theme.palette,
      legend: { top: 0, type: 'scroll', textStyle: { color: theme.text } },
      tooltip: {
        ...base.tooltip,
        valueFormatter: (value: unknown) => formatTL(typeof value === 'number' ? value : null)
      },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: theme.axisLine } },
        axisLabel: { color: theme.text }
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: theme.splitLine } },
        axisLabel: { color: theme.text, formatter: (v: number) => v.toLocaleString('tr-TR') }
      },
      series: offers.map((offer) => ({
        name: offer.store,
        type: 'line',
        step: 'end',
        showSymbol: false,
        lineStyle: { width: 2 },
        data: (offer.history ?? []).filter(([d]) => d >= from)
      }))
    };
  });
</script>

{#snippet otherOffers(offer: CatalogOffer)}
  {#if offer.other_offers?.length}
    <details class="variants">
      <summary>{offer.store} için {offer.other_offers.length} seçenek daha</summary>
      <ul>
        {#each offer.other_offers as other (other.product_id)}
          <li>
            <span class="variant-name">{offerLabel(other)}</span>
            <span class="muted">
              {#if other.last_date !== offer.last_date}son görülme {formatDayTR(other.last_date)}{/if}
            </span>
            <span class="variant-price">{formatTL(other.latest_price)}</span>
          </li>
        {/each}
      </ul>
    </details>
  {/if}
{/snippet}

<svelte:head>
  <title>{data ? `${data.name} fiyatları` : 'Ürün'} – ucuzu</title>
</svelte:head>

{#if item.error}
  <ApiAlert message={item.error} errorMeta={item.errorMeta} />
  <p><a href="/">Ana sayfaya dön</a></p>
{:else if !data}
  <Spinner label="Fiyatlar yükleniyor…" />
{:else}
  <nav class="crumbs" aria-label="Konum">
    <a href="/">Ana sayfa</a><span>›</span>
    <a href={searchHref({ group: data.group })}>{groupLabel(data.group)}</a>
    {#if data.category !== 'Uncategorized'}<span>›</span><span>{data.category}</span>{/if}
  </nav>

  <section class="top">
    <div class="image" style={`--h: ${hue}`} aria-hidden="true">{monogram(data.name)}</div>

    <div class="info">
      <h1>{data.name}</h1>
      <p class="muted">
        {data.summary.current_offer_count} mağazada güncel fiyat · son güncelleme {formatDayTR(data.summary.last_date)}
      </p>

      <div class="best">
        <span class="label">En ucuz fiyat</span>
        <span class="price">{formatTL(data.summary.min_price)}</span>
        {#if best}<span class="store"><Icon name="store" size={16} /> {best.store}</span>{/if}
      </div>

      <dl class="stats">
        <div>
          <dt>En yüksek güncel fiyat</dt>
          <dd>{formatTL(data.summary.max_price)}</dd>
        </div>
        {#if data.summary.lowest_ever}
          <div>
            <dt>Görülen en düşük fiyat</dt>
            <dd>
              {formatTL(data.summary.lowest_ever.price)}
              <span class="muted">({data.summary.lowest_ever.store}, {formatDayTR(data.summary.lowest_ever.date)})</span>
            </dd>
          </div>
        {/if}
        {#if data.summary.min_price && data.summary.max_price && data.summary.max_price > data.summary.min_price}
          <div>
            <dt>Mağazalar arası fark</dt>
            <dd>{formatTL(data.summary.max_price - data.summary.min_price)}</dd>
          </div>
        {/if}
      </dl>

      <div class="alarm">
        {#if alarmFormOpen}
          <form onsubmit={saveAlarm}>
            <label>
              Fiyat bu tutarın altına düşünce haber ver
              <span class="input">
                <input type="number" min="0.01" step="0.01" bind:value={target} required />
                <span>TL</span>
              </span>
            </label>
            <button class="primary" type="submit">Alarmı kur</button>
            <button class="ghost" type="button" onclick={() => (alarmFormOpen = false)}>Vazgeç</button>
          </form>
        {:else if alarm}
          <p class="alarm-set">
            <Icon name="bell" size={18} /> Alarm kurulu: {formatTL(alarm.target)} altı
            <button class="link" type="button" onclick={openAlarmForm}>Değiştir</button>
            <button class="link" type="button" onclick={() => removeAlarm(data.id)}>Kaldır</button>
          </p>
        {:else}
          <button class="primary" type="button" onclick={openAlarmForm}>
            <Icon name="bell" size={18} /> Fiyat alarmı kur
          </button>
        {/if}
      </div>
    </div>
  </section>

  <section class="block">
    <h2>Fiyatlar</h2>
    <ol class="offers">
      {#each current as offer, i (offer.retailer + offer.product_id)}
        <li class:cheapest={i === 0}>
          <div class="offer-store">
            <strong>{offer.store}</strong>
            <span class="muted">{offer.other_offers?.length ? offerLabel(offer) : offer.product_name}</span>
          </div>
          <div class="offer-change">
            {#if changeLabel(offer)}
              <span class:down={offer.previous_price! > offer.latest_price!} class:up={offer.previous_price! < offer.latest_price!}>
                {changeLabel(offer)}
              </span>
              <span class="muted">{formatDayTR(offer.price_since)}</span>
            {/if}
          </div>
          <div class="offer-price">
            {#if i === 0}<span class="tag">En ucuz</span>{/if}
            <strong>{formatTL(offer.latest_price)}</strong>
          </div>
          {@render otherOffers(offer)}
        </li>
      {:else}
        <li class="muted">Bu ürün için güncel fiyat yok.</li>
      {/each}
    </ol>
    {#if stale.length}
      <details class="stale">
        <summary>Güncel olmayan {stale.length} fiyat</summary>
        <ol class="offers">
          {#each stale as offer (offer.retailer + offer.product_id)}
            <li>
              <div class="offer-store">
                <strong>{offer.store}</strong>
                <span class="muted">{offer.other_offers?.length ? offerLabel(offer) : offer.product_name}</span>
              </div>
              <div class="offer-change muted">son görülme {formatDayTR(offer.last_date)}</div>
              <div class="offer-price"><span class="muted">{formatTL(offer.latest_price)}</span></div>
              {@render otherOffers(offer)}
            </li>
          {/each}
        </ol>
      </details>
    {/if}
  </section>

  {#if data.pack_options.length}
    <section class="block">
      <h2>Paket seçenekleri</h2>
      <ol class="offers">
        {#each data.pack_options as option (option.pack)}
          {#each option.offers as offer (offer.retailer + offer.product_id)}
            <li>
              <div class="offer-store">
                <strong>{option.pack} adetlik paket · {offer.store}</strong>
                <span class="muted">{offer.product_name}</span>
              </div>
              <div class="offer-change muted">
                {#if offer.is_current}paket başı {formatTL(offer.price_per_package)}{:else}son görülme {formatDayTR(offer.last_date)}{/if}
              </div>
              <div class="offer-price"><strong>{formatTL(offer.latest_price)}</strong></div>
            </li>
          {/each}
        {/each}
      </ol>
    </section>
  {/if}

  <section class="block">
    <div class="section-head">
      <h2>Fiyat geçmişi</h2>
      <div class="range" role="group" aria-label="Zaman aralığı">
        <button type="button" class:active={range === 30} onclick={() => (range = 30)}>1 ay</button>
        <button type="button" class:active={range === 90} onclick={() => (range = 90)}>3 ay</button>
        <button type="button" class:active={range === 0} onclick={() => (range = 0)}>Tümü</button>
      </div>
    </div>
    <Chart option={chartOption} height={340} ariaLabel={`${data.name} mağaza fiyat geçmişi`} />
  </section>

  {#if sizes.length}
    <section class="block">
      <div class="section-head"><h2>Diğer boyutlar</h2></div>
      <div class="product-grid six">
        {#each sizes as s (s.id)}
          <ProductCard
            href={itemHref(s.id, s.name)}
            name={s.name}
            group={s.group}
            price={s.min_price}
            priceLabel={s.store_count > 1 ? 'en ucuz' : undefined}
            storeLine={s.store_count > 1 ? `${s.store_count} mağazada` : s.store}
          />
        {/each}
      </div>
    </section>
  {/if}

  {#if similar.length}
    <section class="block">
      <div class="section-head"><h2>Benzer ürünler</h2></div>
      <div class="product-grid six">
        {#each similar as s (s.id)}
          <ProductCard
            href={itemHref(s.id, s.name)}
            name={s.name}
            group={s.group}
            price={s.min_price}
            priceLabel={s.store_count > 1 ? 'en ucuz' : undefined}
            storeLine={s.store_count > 1 ? `${s.store_count} mağazada` : s.store}
          />
        {/each}
      </div>
    </section>
  {/if}
{/if}

<style>
  .crumbs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
    color: var(--color-muted-foreground);
    font-size: 0.82rem;
  }
  .crumbs a {
    color: inherit;
    text-decoration: none;
  }
  .top {
    display: grid;
    grid-template-columns: minmax(200px, 340px) 1fr;
    gap: 32px;
    padding: 24px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-panel);
    background: var(--color-card);
  }
  .image {
    display: grid;
    aspect-ratio: 1;
    place-items: center;
    border-radius: var(--radius-control);
    background: hsl(var(--h) 60% 95%);
    color: hsl(var(--h) 45% 38%);
    font-size: 4rem;
    font-weight: 700;
  }
  :global(.dark) .image {
    background: hsl(var(--h) 30% 16%);
    color: hsl(var(--h) 60% 75%);
  }
  .info h1 {
    margin: 0 0 4px;
    font-size: 1.5rem;
  }
  .info > p {
    margin: 0 0 20px;
    font-size: 0.85rem;
  }
  .best {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px 14px;
    padding: 16px 18px;
    border-radius: var(--radius-control);
    background: var(--color-accent-soft);
  }
  .best .label {
    flex-basis: 100%;
    color: var(--color-muted-foreground);
    font-size: 0.8rem;
  }
  .best .price {
    color: var(--color-accent);
    font-size: 2rem;
    font-weight: 700;
  }
  .best .store {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    margin: 18px 0;
  }
  .stats dt {
    color: var(--color-muted-foreground);
    font-size: 0.78rem;
  }
  .stats dd {
    margin: 2px 0 0;
    font-weight: 600;
  }
  .stats dd .muted {
    font-size: 0.78rem;
    font-weight: 400;
  }
  .alarm form {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 10px;
  }
  .alarm label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 0.85rem;
  }
  .input {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .input input {
    width: 140px;
    height: 40px;
    padding: 0 10px;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-control);
    background: var(--color-card);
    color: var(--color-foreground);
  }
  .primary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 40px;
    padding: 0 18px;
    border: 0;
    border-radius: var(--radius-control);
    background: var(--color-accent);
    color: var(--color-on-primary);
    font-weight: 600;
  }
  .ghost {
    height: 40px;
    padding: 0 14px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    background: none;
    color: var(--color-foreground);
  }
  .alarm-set {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin: 0;
    color: var(--color-positive);
    font-weight: 600;
  }
  .link {
    border: 0;
    background: none;
    color: var(--color-accent);
    font-size: 0.85rem;
  }
  .block {
    margin-top: 32px;
  }
  .block > h2 {
    margin: 0 0 14px;
    font-size: 1.25rem;
  }
  .offers {
    margin: 0;
    padding: 0;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-panel);
    background: var(--color-card);
    list-style: none;
  }
  .offers li {
    display: grid;
    grid-template-columns: 1fr auto 160px;
    align-items: center;
    gap: 16px;
    padding: 14px 18px;
    border-top: 1px solid var(--color-border);
  }
  .offers li:first-child {
    border-top: 0;
  }
  .offers li.cheapest {
    background: var(--color-positive-soft);
  }
  .offer-store {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .offer-store .muted {
    overflow: hidden;
    font-size: 0.8rem;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .offer-change {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    font-size: 0.8rem;
  }
  .down {
    color: var(--color-positive);
    font-weight: 600;
  }
  .up {
    color: var(--color-destructive);
    font-weight: 600;
  }
  .offer-price {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    font-size: 1.1rem;
  }
  .tag {
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--color-positive);
    color: #fff;
    font-size: 0.7rem;
    font-weight: 600;
  }
  .variants {
    grid-column: 1 / -1;
    margin-top: -6px;
    font-size: 0.85rem;
  }
  .variants summary {
    width: fit-content;
    color: var(--color-accent);
    cursor: pointer;
  }
  .variants ul {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
  }
  .offers .variants li {
    display: grid;
    grid-template-columns: 1fr auto 160px;
    gap: 16px;
    padding: 6px 0;
    border-top: 1px dashed var(--color-border);
    background: none;
  }
  .variant-name {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .variant-price {
    text-align: right;
  }
  .stale {
    margin-top: 12px;
  }
  .stale summary {
    margin-bottom: 10px;
    color: var(--color-muted-foreground);
    font-size: 0.85rem;
  }
  .range {
    display: flex;
    gap: 4px;
  }
  .range button {
    padding: 5px 12px;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-card);
    color: var(--color-foreground);
    font-size: 0.8rem;
  }
  .range button.active {
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }
  @media (max-width: 760px) {
    .top {
      grid-template-columns: 1fr;
      padding: 16px;
    }
    .image {
      max-height: 180px;
      aspect-ratio: auto;
      height: 160px;
    }
    .offers li,
    .offers .variants li {
      grid-template-columns: 1fr auto;
    }
    .offer-change,
    .variants li .muted {
      display: none;
    }
  }
</style>
