<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import Icon from '$lib/components/Icon.svelte';
  import { groupLabel, searchHref } from '$lib/catalog';
  import { alarms } from '$lib/stores/alarms.svelte';
  import { catalog, loadGroups } from '$lib/stores/catalog.svelte';
  import { effectiveTheme, toggleTheme } from '$lib/themes.svelte';

  /** Shop header: wordmark, category menu, search box, deals/alarms links and a group strip. */

  let query = $state('');
  let menuOpen = $state(false);
  let menu = $state<HTMLDivElement>();

  // Keep the box in sync with the search page's query.
  $effect(() => {
    query = page.url.pathname === '/ara' ? (page.url.searchParams.get('q') ?? '') : '';
  });

  $effect(() => {
    void loadGroups();
  });

  // Close the category menu on navigation.
  $effect(() => {
    void page.url.href;
    menuOpen = false;
  });

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    const group = page.url.pathname === '/ara' ? page.url.searchParams.get('group') : null;
    void goto(searchHref({ q: query.trim(), group }));
  }

  function onWindowClick(event: MouseEvent): void {
    if (menuOpen && menu && !menu.contains(event.target as Node)) menuOpen = false;
  }

  const activeGroup = $derived(page.url.pathname === '/ara' ? page.url.searchParams.get('group') : null);
</script>

<svelte:window onclick={onWindowClick} onkeydown={(e) => e.key === 'Escape' && (menuOpen = false)} />

<header class="site-header">
  <div class="bar container">
    <a class="logo" href="/" aria-label="ucuzu ana sayfa">ucuzu</a>

    <div class="menu" bind:this={menu}>
      <button class="menu-button" type="button" aria-expanded={menuOpen} onclick={() => (menuOpen = !menuOpen)}>
        <Icon name="menu" size={18} />
        <span>Kategoriler</span>
      </button>
      {#if menuOpen}
        <div class="menu-panel" role="menu">
          {#each catalog.groups as group (group.group)}
            <div class="menu-group">
              <a class="menu-title" role="menuitem" href={searchHref({ group: group.group })}>{groupLabel(group.group)}</a>
              <div class="menu-stores">
                {#each group.stores.slice(0, 6) as store (store.retailer)}
                  <a href={searchHref({ group: group.group, store: store.store })}>{store.store}</a>
                {/each}
              </div>
            </div>
          {:else}
            <p class="menu-empty">{catalog.error ?? 'Yükleniyor…'}</p>
          {/each}
        </div>
      {/if}
    </div>

    <form class="search" role="search" onsubmit={submit}>
      <input
        type="search"
        placeholder="Neyi en ucuza almak istersin?"
        aria-label="Ürün ara"
        bind:value={query}
      />
      <button type="submit" aria-label="Ara"><Icon name="search" size={22} /></button>
    </form>

    <nav class="actions" aria-label="Kısayollar">
      <a href="/firsatlar" class:active={page.url.pathname === '/firsatlar'}>
        <Icon name="tag" />
        <span>Fırsatlar</span>
      </a>
      <a href="/alarmlar" class:active={page.url.pathname === '/alarmlar'}>
        <span class="icon-wrap">
          <Icon name="bell" />
          {#if alarms.list.length}<span class="count">{alarms.list.length}</span>{/if}
        </span>
        <span>Fiyat Alarmı</span>
      </a>
      <a href="/analiz">
        <Icon name="chart" />
        <span>Analiz</span>
      </a>
      <button type="button" class="theme" onclick={toggleTheme} aria-label="Temayı değiştir">
        <Icon name={effectiveTheme() === 'dark' ? 'sun' : 'moon'} />
      </button>
    </nav>
  </div>

  {#if catalog.groups.length}
    <nav class="strip container" aria-label="Kategoriler">
      {#each catalog.groups as group (group.group)}
        <a href={searchHref({ group: group.group })} class:active={activeGroup === group.group}>
          {groupLabel(group.group)}
        </a>
      {/each}
    </nav>
  {/if}
</header>

<style>
  .site-header {
    position: sticky;
    top: 0;
    z-index: 20;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-card);
  }
  .bar {
    display: flex;
    align-items: center;
    gap: 16px;
    height: 72px;
  }
  .logo {
    color: var(--color-accent);
    font-size: 1.85rem;
    font-weight: 700;
    letter-spacing: -0.04em;
    text-decoration: none;
  }
  .menu {
    position: relative;
  }
  .menu-button {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 40px;
    padding: 0 14px;
    border: 0;
    border-radius: var(--radius-control);
    background: var(--color-muted);
    color: var(--color-foreground);
    font-size: 0.9rem;
    font-weight: 500;
  }
  .menu-panel {
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(180px, 1fr));
    gap: 18px 28px;
    width: min(760px, calc(100vw - 32px));
    max-height: 70vh;
    padding: 20px 22px;
    overflow: auto;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-panel);
    background: var(--color-card);
    box-shadow: var(--shadow-hover);
  }
  .menu-title {
    display: block;
    margin-bottom: 6px;
    color: var(--color-foreground);
    font-weight: 600;
    text-decoration: none;
  }
  .menu-stores {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .menu-stores a {
    color: var(--color-muted-foreground);
    font-size: 0.85rem;
    text-decoration: none;
  }
  .menu-title:hover,
  .menu-stores a:hover {
    color: var(--color-accent);
  }
  .menu-empty {
    margin: 0;
    color: var(--color-muted-foreground);
  }
  .search {
    display: flex;
    flex: 1;
    min-width: 0;
    height: 48px;
    overflow: hidden;
    border: 2px solid var(--color-accent);
    border-radius: var(--radius-control);
    background: var(--color-card);
  }
  .search input {
    flex: 1;
    min-width: 0;
    padding: 0 16px;
    border: 0;
    outline: none;
    background: transparent;
    color: var(--color-foreground);
    font-size: 0.95rem;
  }
  .search button {
    display: grid;
    width: 76px;
    place-items: center;
    border: 0;
    background: var(--color-accent);
    color: var(--color-on-primary);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .actions a,
  .theme {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 10px;
    border: 0;
    border-radius: var(--radius-control);
    background: none;
    color: var(--color-foreground);
    font-size: 0.75rem;
    font-weight: 500;
    text-decoration: none;
  }
  .actions a:hover,
  .actions a.active,
  .theme:hover {
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }
  .icon-wrap {
    position: relative;
    display: grid;
  }
  .count {
    position: absolute;
    top: -6px;
    right: -10px;
    min-width: 18px;
    padding: 0 5px;
    border-radius: 999px;
    background: var(--color-destructive);
    color: #fff;
    font-size: 0.65rem;
    line-height: 18px;
    text-align: center;
  }
  .strip {
    display: flex;
    gap: 6px;
    padding-bottom: 10px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .strip a {
    flex: none;
    padding: 6px 12px;
    border-radius: 999px;
    color: var(--color-muted-foreground);
    font-size: 0.85rem;
    font-weight: 500;
    text-decoration: none;
  }
  .strip a:hover {
    color: var(--color-foreground);
    background: var(--color-muted);
  }
  .strip a.active {
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }

  @media (max-width: 900px) {
    .bar {
      flex-wrap: wrap;
      height: auto;
      padding-top: 10px;
      padding-bottom: 10px;
      gap: 10px;
    }
    .search {
      order: 3;
      flex-basis: 100%;
    }
    .actions {
      margin-left: auto;
    }
    .actions span:not(.icon-wrap):not(.count) {
      display: none;
    }
    .menu-panel {
      grid-template-columns: repeat(2, minmax(140px, 1fr));
    }
  }
  @media (max-width: 520px) {
    .menu-button span {
      display: none;
    }
    .menu-panel {
      grid-template-columns: 1fr;
    }
  }
</style>
