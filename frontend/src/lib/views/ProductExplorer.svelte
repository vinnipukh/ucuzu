<script lang="ts">
  import SearchableSelect from '$lib/components/SearchableSelect.svelte';
  import Chart from '$lib/components/Chart.svelte';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import DataTable, { type Column } from '$lib/components/DataTable.svelte';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import Spinner from '$lib/components/Spinner.svelte';
  import { fetchApi } from '$lib/api/client';
  import { AsyncResource } from '$lib/utils/async.svelte';
  import { formatCurrency, formatPercent, formatDate } from '$lib/utils/format';
  import { productPriceOption, monthlyAverageOption, type MonthlyAveragePoint } from '$lib/utils/chartOptions.svelte';
  import type { ProductHistoryData, HistoryMeta, ProductDetailData, ProductListGroup, ProductListMeta } from '$lib/types/api';
  import { filters, buildQueryMap } from '$lib/stores/filters.svelte';

  // Product names per retailer for the pickers (/api/products), not the full history.
  const optionsResource = new AsyncResource<ProductListGroup[], ProductListMeta>();
  const productResource = new AsyncResource<ProductHistoryData, HistoryMeta>();
  // Monthly averages use the fast SQLite-backed /api/product when available.
  const monthlyDetailResource = new AsyncResource<ProductDetailData, Record<string, unknown>>();
  // CSV-only fallback: full-range /api/history for the product.
  const monthlyFallbackResource = new AsyncResource<ProductHistoryData, HistoryMeta>();

  let selectedRetailer = $state<string | null>(null);
  let selectedProduct = $state<string | null>(null);
  // The daily price graph is optional; the monthly average is the default view.
  let showDailyChart = $state(false);

  const returnedRetailers = $derived.by<string[]>(() => {
    const groups = optionsResource.value ?? [];
    return groups.map((group) => group.retailer).sort();
  });

  const retailerChoices = $derived.by<string[]>(() => {
    const preferred =
      filters.selectedRetailers.length > 0
        ? filters.selectedRetailers.filter((name) => returnedRetailers.includes(name))
        : [];
    return preferred.length ? preferred : returnedRetailers;
  });

  const productChoices = $derived.by<string[]>(() => {
    const group = optionsResource.value?.find((entry) => entry.retailer === selectedRetailer);
    return group ? [...group.products].sort() : [];
  });

  const summary = $derived(productResource.value?.summary ?? null);
  const productHistory = $derived(productResource.value?.history ?? []);
  const chartOption = $derived(
    selectedProduct && selectedRetailer
      ? productPriceOption(productHistory, `${selectedProduct} at ${selectedRetailer}`)
      : undefined
  );

  // Monthly averages over the FULL observed history of the product (months on
  // the X axis, average price on the Y axis). Independent of the date filter.
  const monthlyPoints = $derived.by<{ date: string; price: number | null }[]>(() => {
    const detail = monthlyDetailResource.value;
    if (detail && detail.history) return detail.history;
    if (detail && detail.price_history) {
      return Object.entries(detail.price_history).map(([date, price]) => ({ date, price }));
    }
    return monthlyFallbackResource.value?.history ?? [];
  });

  const monthlyError = $derived(monthlyDetailResource.error ?? monthlyFallbackResource.error);
  const monthlyLoading = $derived(
    (monthlyDetailResource.loading || monthlyFallbackResource.loading) && !monthlyDetailResource.value && !monthlyFallbackResource.value
  );

  const monthlyAverages = $derived.by<MonthlyAveragePoint[]>(() => {
    const history = monthlyPoints;
    const byMonth = new Map<string, { sum: number; count: number }>();
    for (const point of history) {
      if (point.price === null || point.price === undefined || Number.isNaN(point.price)) continue;
      const month = point.date.slice(0, 7); // YYYY-MM from ISO date
      if (!/^\d{4}-\d{2}$/.test(month)) continue;
      const entry = byMonth.get(month) ?? { sum: 0, count: 0 };
      entry.sum += point.price;
      entry.count += 1;
      byMonth.set(month, entry);
    }
    return [...byMonth.entries()]
      .map(([month, { sum, count }]) => ({ month, avg: sum / count }))
      .sort((a, b) => a.month.localeCompare(b.month));
  });

  const monthlyChartOption = $derived(
    selectedProduct && selectedRetailer && monthlyAverages.length > 0
      ? monthlyAverageOption(monthlyAverages, `Monthly average price — ${selectedProduct} at ${selectedRetailer}`)
      : undefined
  );

  const queryKey = $derived(JSON.stringify(buildQueryMap()));

  // Reload the product option list whenever the retailers or dates change.
  $effect(() => {
    void queryKey;
    const query = {
      retailer: [...filters.selectedRetailers],
      start_date: filters.startDate ?? '',
      end_date: filters.endDate ?? ''
    };
    optionsResource.run(() => fetchApi<ProductListGroup[], ProductListMeta>('/api/products', query));
  });

  // Keep selections valid as the option list changes.
  $effect(() => {
    const choices = retailerChoices;
    if (!selectedRetailer || !choices.includes(selectedRetailer)) {
      selectedRetailer = choices[0] ?? null;
    }
    const products = productChoices;
    if (selectedRetailer && (!selectedProduct || !products.includes(selectedProduct))) {
      selectedProduct = products[0] ?? null;
    }
  });

  // Load the focused product series (respects the date-range filter).
  $effect(() => {
    if (!selectedRetailer || !selectedProduct) return;
    // Only the product's retailer: the server loads that retailer's history, not the whole selection.
    const query = {
      ...buildQueryMap(),
      retailer: [selectedRetailer],
      product_name: selectedProduct,
      product_retailer: selectedRetailer
    };
    productResource.run(() => fetchApi<ProductHistoryData, HistoryMeta>('/api/history', query));
  });

  // Fast SQLite-backed product detail for the monthly-average chart.
  $effect(() => {
    if (!selectedRetailer || !selectedProduct) return;
    monthlyDetailResource.run(() =>
      fetchApi<ProductDetailData, Record<string, unknown>>('/api/product', {
        product_name: selectedProduct,
        retailer: selectedRetailer
      })
    );
  });

  // CSV-only fallback: full-range /api/history for the product.
  $effect(() => {
    if (!selectedRetailer || !selectedProduct) return;
    if (!monthlyDetailResource.error) return;
    const query = {
      retailer: [selectedRetailer],
      start_date: filters.inventoryMinDate?.slice(0, 10) ?? '',
      end_date: filters.inventoryMaxDate?.slice(0, 10) ?? '',
      max_files: 0,
      all_history: true,
      product_name: selectedProduct,
      product_retailer: selectedRetailer
    };
    monthlyFallbackResource.run(() => fetchApi<ProductHistoryData, HistoryMeta>('/api/history', query));
  });

  // 'Uncategorized' is the pipeline's fill-in for sources without a category
  // column (Gurmar, HomeGoods); it is not real data, so blank it in the UI.
  function categoryDisplay(value: unknown): string {
    const raw = String(value ?? '');
    return raw === '' || raw === 'Uncategorized' ? '—' : raw;
  }

  const productColumns: Column[] = [
    { key: 'date', label: 'Date', format: (v) => formatDate(String(v)) },
    { key: 'price', label: 'Price (TRY)', align: 'right', monospace: true, format: (v) => formatCurrency(Number(v)) },
    { key: 'category', label: 'Category', format: categoryDisplay },
    { key: 'source_file', label: 'Source file' }
  ];
</script>

<section class="view">
  <h2 class="view-title">1. Product price explorer</h2>

  {#if optionsResource.error}
    <ApiAlert message={optionsResource.error} errorMeta={optionsResource.errorMeta} />
  {:else if optionsResource.loading && !optionsResource.value}
    <Spinner label="Loading product options from /api/products…" />
  {:else if optionsResource.value}
    <div class="controls">
      <SearchableSelect
        label="Retailer"
        options={retailerChoices}
        value={selectedRetailer}
        placeholder="Type a few letters; misspellings are okay"
        help="Search supports close matches, so small typos still guide you to the right retailer."
        onSelect={(value) => (selectedRetailer = value)}
      />
      <SearchableSelect
        label="Product"
        options={productChoices}
        value={selectedProduct}
        placeholder="Type a few letters; misspellings are okay"
        help="Products seen at this retailer in the selected date range."
        onSelect={(value) => (selectedProduct = value)}
      />
    </div>

    {#if productResource.error}
      <ApiAlert message={productResource.error} errorMeta={productResource.errorMeta} />
    {:else if productResource.loading && !productResource.value}
      <Spinner label="Loading price history…" />
    {:else if productHistory.length > 0 && summary}
      <div class="metrics">
        <MetricCard label="Latest price" value={formatCurrency(summary.latest_price)} tone="default" />
        <MetricCard label="Cheapest price" value={formatCurrency(summary.cheapest_price)} tone="positive" />
        <MetricCard label="Cheapest date" value={formatDate(summary.cheapest_date)} />
        <MetricCard
          label="Change since first"
          value={formatPercent(summary.change_since_first_pct)}
          tone={(summary.change_since_first_pct ?? 0) < 0 ? 'positive' : (summary.change_since_first_pct ?? 0) > 0 ? 'negative' : 'default'}
        />
      </div>

      <div class="monthly">
        <h3 class="chart-subheading">Monthly average price</h3>
        {#if monthlyError}
          <ApiAlert message={monthlyError} errorMeta={monthlyDetailResource.errorMeta ?? monthlyFallbackResource.errorMeta} />
        {:else if monthlyLoading}
          <Spinner label="Loading full product history for monthly averages…" inline />
        {:else if monthlyChartOption}
          <Chart option={monthlyChartOption} loading={monthlyLoading} ariaLabel="Monthly average price chart" />
          <p class="caption">
            Average price per month ({monthlyAverages.length} month{monthlyAverages.length === 1 ? '' : 's'}) over the
            full observed history — not affected by the date-range filter.
          </p>
        {:else}
          <p class="empty">No monthly averages available for this product.</p>
        {/if}
      </div>

      <div class="daily">
        <div class="daily-head">
          <h3 class="chart-subheading">Daily price history</h3>
          <label class="toggle">
            <input type="checkbox" bind:checked={showDailyChart} />
            <span>Show daily chart</span>
          </label>
        </div>
        {#if showDailyChart}
          {#if chartOption}
            <Chart option={chartOption} loading={productResource.loading} ariaLabel="Product price history chart" />
          {:else}
            <p class="empty">No price history was returned for this product and filter selection.</p>
          {/if}
        {:else}
          <p class="caption">Daily chart hidden — enable “Show daily chart” to display it.</p>
        {/if}
      </div>

      <DataTable
        columns={productColumns}
        rows={productHistory as unknown as Record<string, unknown>[]}
        emptyMessage="No price history was returned for this product and filter selection."
      />

      {#if (productResource.meta?.warnings ?? []).length > 0}
        <div class="warnings">
          {#each productResource.meta!.warnings! as warning (warning)}
            <ApiAlert message={warning} role="warning" />
          {/each}
        </div>
      {/if}
    {:else if !productResource.loading}
      <p class="empty">No price history was returned for this product and filter selection.</p>
    {/if}
  {/if}
</section>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  .view-title {
    margin: 0;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-foreground);
    font-size: 1rem;
    font-weight: 600;
  }
  .controls {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
    padding: 16px;
    border: 1px solid var(--color-border);
    border-radius: 16px;
    background: var(--color-muted);
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }
  .monthly,
  .daily {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px;
    border: 1px solid var(--color-border);
    border-radius: 16px;
    background: var(--color-card);
  }
  .daily-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    color: var(--color-muted-foreground);
    cursor: pointer;
    font-size: 0.78rem;
  }
  .toggle input {
    width: 14px;
    height: 14px;
    accent-color: var(--color-accent);
    cursor: pointer;
  }
  .chart-subheading {
    margin: 0;
    color: var(--color-foreground);
    font-family: var(--font-mono);
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .caption {
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.75rem;
  }
  .warnings {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .empty {
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.86rem;
  }
  @media (max-width: 640px) {
    .controls {
      grid-template-columns: 1fr;
    }
  }
</style>
