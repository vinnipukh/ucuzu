<script lang="ts">
  import SiteHeader from '$lib/components/SiteHeader.svelte';
  import { groupLabel, searchHref } from '$lib/catalog';
  import { catalog } from '$lib/stores/catalog.svelte';

  let { children } = $props();
</script>

<SiteHeader />

<main class="container">
  {@render children()}
</main>

<footer class="site-footer">
  <div class="container footer-inner">
    <div>
      <p class="brand">ucuzu</p>
      <p class="muted">
        Fiyatlar mağaza sitelerinden düzenli aralıklarla toplanır; gösterilen fiyat her mağazanın en son gözlenen
        fiyatıdır. Aynı adı taşıyan ürünler mağazalar arasında karşılaştırılır.
      </p>
    </div>
    <nav aria-label="Kategoriler">
      {#each catalog.groups.slice(0, 8) as group (group.group)}
        <a href={searchHref({ group: group.group })}>{groupLabel(group.group)}</a>
      {/each}
    </nav>
    <nav aria-label="Sayfalar">
      <a href="/firsatlar">Fiyatı düşenler</a>
      <a href="/alarmlar">Fiyat alarmları</a>
      <a href="/analiz">Enflasyon analizi</a>
    </nav>
  </div>
</footer>

<style>
  main {
    min-height: 60vh;
    padding-top: 24px;
    padding-bottom: 48px;
  }
  .site-footer {
    border-top: 1px solid var(--color-border);
    background: var(--color-card);
    font-size: 0.85rem;
  }
  .footer-inner {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    gap: 32px;
    padding-top: 32px;
    padding-bottom: 40px;
  }
  .brand {
    margin: 0 0 6px;
    color: var(--color-accent);
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: -0.04em;
  }
  .footer-inner p {
    max-width: 52ch;
    margin-top: 0;
  }
  nav {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  nav a {
    color: var(--color-muted-foreground);
    text-decoration: none;
  }
  nav a:hover {
    color: var(--color-accent);
  }
  @media (max-width: 720px) {
    .footer-inner {
      grid-template-columns: 1fr 1fr;
    }
    .footer-inner > div {
      grid-column: 1 / -1;
    }
  }
</style>
