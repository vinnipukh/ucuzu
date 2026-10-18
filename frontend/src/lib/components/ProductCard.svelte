<script lang="ts">
  import { formatTL, groupLabel, hueOf, monogram } from '$lib/catalog';

  /**
   * Product tile for grids: monogram placeholder, name, price and store line.
   * `oldPrice`/`dropPercent` show a price-drop badge.
   */
  interface Props {
    href: string;
    name: string;
    group: string;
    price: number | null;
    priceLabel?: string;
    oldPrice?: number | null;
    dropPercent?: number | null;
    storeLine: string;
  }

  let { href, name, group, price, priceLabel, oldPrice = null, dropPercent = null, storeLine }: Props = $props();

  const hue = $derived(hueOf(name));
</script>

<a class="card" {href}>
  <div class="thumb" style={`--h: ${hue}`}>
    <span>{monogram(name)}</span>
    {#if dropPercent}
      <span class="badge">%{Math.round(dropPercent)} düştü</span>
    {/if}
  </div>
  <div class="body">
    <p class="group">{groupLabel(group)}</p>
    <h3 class="name" title={name}>{name}</h3>
    <div class="price-row">
      {#if priceLabel}<span class="price-label">{priceLabel}</span>{/if}
      <span class="price">{formatTL(price)}</span>
      {#if oldPrice}<s class="old">{formatTL(oldPrice)}</s>{/if}
    </div>
    <p class="stores">{storeLine}</p>
  </div>
</a>

<style>
  .card {
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-panel);
    background: var(--color-card);
    color: inherit;
    text-decoration: none;
    transition:
      box-shadow 0.15s ease,
      border-color 0.15s ease;
  }
  .card:hover {
    border-color: var(--color-line);
    box-shadow: var(--shadow-hover);
  }
  .thumb {
    position: relative;
    display: grid;
    aspect-ratio: 4 / 3;
    place-items: center;
    background: hsl(var(--h) 60% 95%);
    color: hsl(var(--h) 45% 38%);
    font-size: 1.9rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  :global(.dark) .thumb {
    background: hsl(var(--h) 30% 16%);
    color: hsl(var(--h) 60% 75%);
  }
  .badge {
    position: absolute;
    top: 10px;
    left: 10px;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--color-positive);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0;
  }
  .body {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 4px;
    padding: 12px 14px 14px;
  }
  .group {
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.72rem;
    font-weight: 500;
  }
  .name {
    display: -webkit-box;
    min-height: 2.6em;
    margin: 0;
    overflow: hidden;
    font-family: var(--font-sans);
    font-size: 0.9rem;
    font-weight: 500;
    line-height: 1.3;
    letter-spacing: 0;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
  }
  .price-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
    margin-top: auto;
    padding-top: 6px;
  }
  .price-label {
    color: var(--color-muted-foreground);
    font-size: 0.72rem;
  }
  .price {
    font-size: 1.1rem;
    font-weight: 700;
  }
  .old {
    color: var(--color-muted-foreground);
    font-size: 0.8rem;
  }
  .stores {
    margin: 0;
    overflow: hidden;
    color: var(--color-accent);
    font-size: 0.78rem;
    font-weight: 500;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
</style>
