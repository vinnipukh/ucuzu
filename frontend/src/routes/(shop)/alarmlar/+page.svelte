<script lang="ts">
  import { fetchApi } from '$lib/api/client';
  import Icon from '$lib/components/Icon.svelte';
  import { formatDayTR, formatTL, itemHref } from '$lib/catalog';
  import { alarms, removeAlarm } from '$lib/stores/alarms.svelte';
  import type { CatalogItem } from '$lib/types/api';

  interface Status {
    price: number | null;
    store: string | null;
    error: boolean;
  }

  let status = $state<Record<number, Status>>({});

  // Fetch each alarm's current lowest price once.
  $effect(() => {
    for (const alarm of alarms.list) {
      if (status[alarm.id]) continue;
      status[alarm.id] = { price: null, store: null, error: false };
      fetchApi<CatalogItem>('/api/catalog/item', { id: alarm.id })
        .then((r) => {
          const best = r.data.offers.find((o) => o.is_current) ?? null;
          status[alarm.id] = { price: r.data.summary.min_price, store: best?.store ?? null, error: false };
        })
        .catch(() => (status[alarm.id] = { price: null, store: null, error: true }));
    }
  });

  const reached = $derived(
    alarms.list.filter((a) => {
      const price = status[a.id]?.price;
      return price !== null && price !== undefined && price <= a.target;
    }).length
  );
</script>

<svelte:head>
  <title>Fiyat alarmları – ucuzu</title>
</svelte:head>

<div class="head">
  <h1>Fiyat alarmları</h1>
  <p class="muted">
    Alarmlar bu tarayıcıda saklanır. Ürünün en ucuz güncel fiyatı hedefinize indiğinde burada işaretlenir.
  </p>
</div>

{#if alarms.list.length === 0}
  <div class="empty">
    <Icon name="bell" size={40} />
    <p><strong>Henüz alarm kurmadınız.</strong></p>
    <p class="muted">Bir ürün sayfasında “Fiyat alarmı kur” düğmesini kullanın.</p>
    <a class="primary" href="/">Ürünlere göz at</a>
  </div>
{:else}
  {#if reached}
    <p class="banner"><Icon name="bell" size={18} /> {reached} ürün hedef fiyatınıza indi.</p>
  {/if}
  <ul class="list">
    {#each alarms.list as alarm (alarm.id)}
      {@const s = status[alarm.id]}
      {@const hit = s?.price != null && s.price <= alarm.target}
      <li class:hit>
        <div class="name">
          <a href={itemHref(alarm.id, alarm.name)}>{alarm.name}</a>
          <span class="muted">Kuruldu: {formatDayTR(alarm.createdAt)} · o günkü fiyat {formatTL(alarm.priceWhenSet)}</span>
        </div>
        <div class="num">
          <span class="muted">Hedef</span>
          <strong>{formatTL(alarm.target)}</strong>
        </div>
        <div class="num">
          <span class="muted">Şu an en ucuz</span>
          {#if !s}
            <span class="muted">…</span>
          {:else if s.error}
            <span class="muted">alınamadı</span>
          {:else}
            <strong class:ok={hit}>{formatTL(s.price)}</strong>
            {#if s.store}<span class="muted">{s.store}</span>{/if}
          {/if}
        </div>
        <div class="state">
          {#if hit}<span class="tag">Hedefe ulaştı</span>{:else if s && !s.error}<span class="muted">Bekleniyor</span>{/if}
        </div>
        <button type="button" class="remove" aria-label={`${alarm.name} alarmını kaldır`} onclick={() => removeAlarm(alarm.id)}>
          <Icon name="x" size={18} />
        </button>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .head h1 {
    margin: 0 0 4px;
    font-size: 1.5rem;
  }
  .head p {
    margin: 0 0 20px;
  }
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 56px 16px;
    border: 1px dashed var(--color-line);
    border-radius: var(--radius-panel);
    color: var(--color-muted-foreground);
    text-align: center;
  }
  .empty p {
    margin: 6px 0;
  }
  .empty strong {
    color: var(--color-foreground);
  }
  .primary {
    margin-top: 14px;
    padding: 10px 18px;
    border-radius: var(--radius-control);
    background: var(--color-accent);
    color: var(--color-on-primary);
    font-weight: 600;
    text-decoration: none;
  }
  .banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-radius: var(--radius-control);
    background: var(--color-positive-soft);
    color: var(--color-positive);
    font-weight: 600;
  }
  .list {
    margin: 0;
    padding: 0;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-panel);
    background: var(--color-card);
    list-style: none;
  }
  .list li {
    display: grid;
    grid-template-columns: 1fr 130px 150px 120px 36px;
    align-items: center;
    gap: 14px;
    padding: 14px 18px;
    border-top: 1px solid var(--color-border);
  }
  .list li:first-child {
    border-top: 0;
  }
  .list li.hit {
    background: var(--color-positive-soft);
  }
  .name {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .name a {
    color: var(--color-foreground);
    font-weight: 600;
    text-decoration: none;
  }
  .name a:hover {
    color: var(--color-accent);
  }
  .name .muted,
  .num .muted {
    font-size: 0.78rem;
  }
  .num {
    display: flex;
    flex-direction: column;
  }
  .ok {
    color: var(--color-positive);
  }
  .tag {
    padding: 3px 10px;
    border-radius: 999px;
    background: var(--color-positive);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .remove {
    display: grid;
    width: 36px;
    height: 36px;
    place-items: center;
    border: 0;
    border-radius: 50%;
    background: none;
    color: var(--color-muted-foreground);
  }
  .remove:hover {
    background: var(--color-muted);
    color: var(--color-destructive);
  }
  @media (max-width: 760px) {
    .list li {
      grid-template-columns: 1fr 1fr 36px;
    }
    .name {
      grid-column: 1 / -1;
    }
    .state {
      display: none;
    }
  }
</style>
