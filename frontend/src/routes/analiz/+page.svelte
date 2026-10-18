<script lang="ts">
  import { onMount } from 'svelte';
  import Header from '$lib/components/Header.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import Spinner from '$lib/components/Spinner.svelte';
  import ProductExplorer from '$lib/views/ProductExplorer.svelte';
  import RetailerAverages from '$lib/views/RetailerAverages.svelte';
  import PriceMovers from '$lib/views/PriceMovers.svelte';
  import CoverageOverview from '$lib/views/CoverageOverview.svelte';
  import EpeyKatfgMonthly from '$lib/views/EpeyKatfgMonthly.svelte';
  import { fetchApi } from '$lib/api/client';
  import { resetFilters, initInventory, filters } from '$lib/stores/filters.svelte';
  import type { InventoryData, InventoryMeta } from '$lib/types/api';

  type Tab = 'product' | 'retailer' | 'movers' | 'coverage' | 'epeykatfg';

  let tab = $state<Tab>('product');
  let inventoryError = $state<string | null>(null);
  let inventoryErrorMeta = $state<Record<string, unknown> | null>(null);
  let inventoryLoading = $state(false);
  const inventoryWarnings = $state<string[]>([]);
  let connected = $state<boolean | null>(null);
  let checking = $state(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'product', label: 'Product explorer' },
    { id: 'retailer', label: 'Retailer averages' },
    { id: 'movers', label: 'Price movers' },
    { id: 'coverage', label: 'Coverage overview' },
    { id: 'epeykatfg', label: 'EpeyKatfg monthly' }
  ];

  async function loadInventory(): Promise<void> {
    inventoryError = null;
    inventoryErrorMeta = null;
    inventoryLoading = true;
    inventoryWarnings.length = 0;
    try {
      const response = await fetchApi<InventoryData, InventoryMeta>('/api/inventory');
      initInventory(response.data.retailers, response.data.min_date, response.data.max_date);
      filters.inventoryFileCount = Number(response.meta.inventory_file_count ?? response.meta.file_count ?? null);
      for (const warning of response.meta.warnings ?? []) inventoryWarnings.push(warning);
      connected = true;
    } catch (err) {
      resetFilters();
      connected = false;
      inventoryError = err instanceof Error ? err.message : String(err);
      inventoryErrorMeta = err && typeof err === 'object' && 'meta' in err ? (err as { meta?: Record<string, unknown> }).meta ?? null : null;
    } finally {
      inventoryLoading = false;
    }
  }

  async function checkHealth(): Promise<void> {
    checking = true;
    try {
      await fetchApi('/api/health');
      connected = true;
    } catch {
      connected = false;
    } finally {
      checking = false;
    }
  }

  function handleApiUrl(url: string): void {
    filters.apiBaseUrl = url;
    void loadInventory();
    void checkHealth();
  }

  function selectTab(id: Tab): void {
    tab = id;
  }

  function onKeydownTab(event: KeyboardEvent): void {
    const index = tabs.findIndex((t) => t.id === tab);
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      tab = tabs[(index + 1) % tabs.length].id;
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      tab = tabs[(index - 1 + tabs.length) % tabs.length].id;
    } else if (event.key === 'Home') {
      event.preventDefault();
      tab = tabs[0].id;
    } else if (event.key === 'End') {
      event.preventDefault();
      tab = tabs[tabs.length - 1].id;
    }
  }

  onMount(() => {
    void loadInventory();
    void checkHealth();
  });
</script>

<svelte:head>
  <title>Inflation Study Dashboard</title>
</svelte:head>

<div class="shell">
  <Header {connected} {checking} onRetry={() => void checkHealth()} />

  {#if inventoryLoading && !filters.inventoryReady}
    <div class="boot-state paper-panel">
      <Spinner label="Loading inventory from the Falcon API…" />
    </div>
  {:else if inventoryError}
    <div class="boot-state paper-panel">
      <ApiAlert message={inventoryError} errorMeta={inventoryErrorMeta} />
      <p class="boot-hint">
        Make sure the Falcon API is running (see <code>docs/GETTING-STARTED.md</code>) and that the base URL above is
        reachable from the browser.
      </p>
    </div>
  {:else if filters.inventoryReady}
    <div class="layout">
      <Sidebar onApplyApiUrl={handleApiUrl} {inventoryWarnings} />

      <main class="main">
        <div class="workspace-head">
          <div>
            <p class="paper-kicker">product / retailer / category index</p>
            <p class="workspace-title">Market workspace</p>
          </div>
          <p class="workspace-note">Choose a view, then tune the data rail on the left.</p>
        </div>

        <div class="tabs-frame">
          <span class="tabs-label">Explore</span>
          <div class="tabs" role="tablist" aria-label="Dashboard sections" tabindex="0" onkeydown={onKeydownTab}>
            {#each tabs as item (item.id)}
              <button
                type="button"
                role="tab"
                id={`tab-${item.id}`}
                aria-selected={tab === item.id}
                aria-controls={`panel-${item.id}`}
                class:active={tab === item.id}
                onclick={() => selectTab(item.id)}
              >
                {item.label}
              </button>
            {/each}
          </div>
        </div>

        <div class="tab-panels">
          <div role="tabpanel" id="panel-product" aria-labelledby="tab-product" hidden={tab !== 'product'}>
            {#if tab === 'product'}<ProductExplorer />{/if}
          </div>
          <div role="tabpanel" id="panel-retailer" aria-labelledby="tab-retailer" hidden={tab !== 'retailer'}>
            {#if tab === 'retailer'}<RetailerAverages />{/if}
          </div>
          <div role="tabpanel" id="panel-movers" aria-labelledby="tab-movers" hidden={tab !== 'movers'}>
            {#if tab === 'movers'}<PriceMovers />{/if}
          </div>
          <div role="tabpanel" id="panel-coverage" aria-labelledby="tab-coverage" hidden={tab !== 'coverage'}>
            {#if tab === 'coverage'}<CoverageOverview />{/if}
          </div>
          <div role="tabpanel" id="panel-epeykatfg" aria-labelledby="tab-epeykatfg" hidden={tab !== 'epeykatfg'}>
            {#if tab === 'epeykatfg'}<EpeyKatfgMonthly />{/if}
          </div>
        </div>
      </main>
    </div>
  {/if}
</div>

<style>
  .shell {
    width: min(100%, 1480px);
    margin: 0 auto;
    padding: 24px 28px 64px;
  }
  .boot-state {
    display: flex;
    flex-direction: column;
    gap: 14px;
    align-items: flex-start;
    width: min(100%, 760px);
    margin: 32px auto;
    padding: 30px;
  }
  .boot-hint {
    max-width: 680px;
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.88rem;
  }
  .boot-hint code {
    padding: 2px 6px;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 0.82rem;
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(260px, 300px) minmax(0, 1fr);
    gap: 20px;
    align-items: start;
  }
  .main {
    min-width: 0;
    padding: clamp(20px, 3vw, 34px);
    border: 1px solid var(--color-line);
    border-radius: var(--radius-panel);
    background: var(--color-card);
    box-shadow: var(--shadow-paper);
  }
  .workspace-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    padding-bottom: 22px;
    border-bottom: 1px solid var(--color-border);
  }
  .workspace-title {
    margin: 7px 0 0;
    color: var(--color-foreground);
    font-family: var(--font-display);
    font-size: clamp(1.1rem, 2vw, 1.45rem);
    font-weight: 600;
    letter-spacing: -0.04em;
  }
  .workspace-note {
    max-width: 300px;
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.8rem;
    text-align: right;
  }
  .tabs-frame {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 22px 0 28px;
    padding: 10px 12px 10px 16px;
    border: 1px solid var(--color-border);
    border-radius: 16px;
    background: var(--color-muted);
  }
  .tabs-label {
    flex: none;
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .tabs {
    display: flex;
    min-width: 0;
    flex: 1;
    gap: 6px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar {
    display: none;
  }
  .tabs button {
    flex: none;
    appearance: none;
    padding: 9px 12px;
    border: 1px solid transparent;
    border-radius: 10px;
    background: transparent;
    color: var(--color-muted-foreground);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 0.74rem;
    font-weight: 500;
    line-height: 1.2;
    white-space: nowrap;
    transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
  }
  .tabs button:hover {
    border-color: var(--color-border);
    color: var(--color-foreground);
    transform: translateY(-1px);
  }
  .tabs button.active {
    border-color: var(--color-line);
    background: var(--color-primary);
    color: var(--color-on-primary);
    box-shadow: var(--shadow-paper-small);
  }
  .tab-panels {
    min-width: 0;
  }
  .tab-panels > div[role='tabpanel'] {
    min-width: 0;
  }
  @media (max-width: 1024px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 700px) {
    .shell {
      padding: 16px 14px 42px;
    }
    .workspace-head {
      align-items: flex-start;
      flex-direction: column;
      gap: 10px;
    }
    .workspace-note {
      max-width: none;
      text-align: left;
    }
    .tabs-frame {
      align-items: flex-start;
      flex-direction: column;
      gap: 8px;
      padding: 12px;
    }
    .tabs {
      width: 100%;
    }
  }
</style>
