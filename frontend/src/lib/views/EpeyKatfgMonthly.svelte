<script lang="ts">
  import Chart from '$lib/components/Chart.svelte';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import DataTable, { type Column } from '$lib/components/DataTable.svelte';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import Spinner from '$lib/components/Spinner.svelte';
  import { fetchApi } from '$lib/api/client';
  import { AsyncResource } from '$lib/utils/async.svelte';
  import { formatPercent, formatInt } from '$lib/utils/format';
  import { monthlyInflationOption } from '$lib/utils/chartOptions.svelte';
  import type { MonthlyInflationRecord, MonthlyInflationMeta } from '$lib/types/api';

  const resource = new AsyncResource<MonthlyInflationRecord[], MonthlyInflationMeta>();

  $effect(() => {
    resource.run(() => fetchApi<MonthlyInflationRecord[], MonthlyInflationMeta>('/api/epeykatfg/monthly-inflation'));
  });

  const rows = $derived(resource.value ?? []);
  const meta = $derived(resource.meta);
  const latest = $derived(rows.length > 0 ? rows[rows.length - 1] : null);
  const previous = $derived(rows.length > 1 ? rows[rows.length - 2] : null);

  const meanMonthly = $derived.by<number | null>(() => {
    const values = rows.map((r) => r.avg_inflation).filter((v): v is number => v !== null && v !== undefined);
    if (values.length === 0) return null;
    return values.reduce((a, b) => a + b, 0) / values.length;
  });

  const chartOption = $derived(
    monthlyInflationOption(rows, 'Monthly inflation — EpeyKatfg basket (%)')
  );

  const columns: Column[] = [
    { key: 'month', label: 'Month', monospace: true },
    { key: 'prev_month', label: 'vs', monospace: true },
    { key: 'n_matched', label: 'n matched', align: 'right', monospace: true, format: (v) => formatInt(Number(v)) },
    { key: 'avg_inflation', label: 'avg %', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) },
    { key: 'basic_index', label: 'basic %', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) },
    { key: 'tuik_weighted', label: 'TUIK-w %', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) },
    { key: 'median_inflation_nonzero', label: 'median nz %', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) },
    { key: 'pct_increased', label: 'inc %', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) },
    { key: 'pct_decreased', label: 'dec %', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) },
    { key: 'covered_weight', label: 'cov w', align: 'right', monospace: true, format: (v) => formatPercent(Number(v)) }
  ];

  const notes = $derived(meta?.notes ?? 'TUIK 2026 weights normalised to 100% over covered groups.');
</script>

<section class="view">
  <h2 class="view-title">5. EpeyKatfg monthly inflation</h2>

  {#if resource.error}
    <ApiAlert message={resource.error} errorMeta={resource.errorMeta} />
  {:else if resource.loading && !resource.value}
    <Spinner label="Loading EpeyKatfg monthly inflation…" />
  {:else if rows.length > 0}
    <p class="context">
      Month-over-month inflation from epey.com daily lowest-price history (2,134 tracked products).
      TUIK 2026 weights are normalised to 100% over the covered groups (03, 05, 06, 08, 09, 13).
    </p>

    <div class="metrics">
      <MetricCard label="Months covered" value={formatInt(rows.length)} />
      <MetricCard label="Latest month" value={latest?.month ?? '-'} />
      <MetricCard label="Latest avg inflation" value={formatPercent(latest?.avg_inflation ?? null)} />
      <MetricCard label="Latest TUIK-weighted" value={formatPercent(latest?.tuik_weighted ?? null)} />
      <MetricCard label="Mean monthly avg" value={formatPercent(meanMonthly)} />
      <MetricCard label="Covered TUIK weight" value={formatPercent(latest?.covered_weight ?? null)} />
    </div>

    <div class="panel">
      <Chart option={chartOption} loading={resource.loading} ariaLabel="Monthly inflation line chart" />
    </div>

    <div class="panel">
      <DataTable
        columns={columns}
        rows={rows as unknown as Record<string, unknown>[]}
        emptyMessage="No monthly inflation records returned."
      />
    </div>

    <p class="context note">{{notes}}</p>
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
  .context {
    max-width: 820px;
    margin: 0;
    padding: 13px 15px;
    border-left: 3px solid var(--color-accent);
    border-radius: 0 11px 11px 0;
    background: var(--color-accent-soft);
    color: var(--color-foreground);
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .note {
    color: var(--color-muted-foreground);
    font-style: italic;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }
  .panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border: 1px solid var(--color-border);
    border-radius: 16px;
    background: var(--color-card);
  }
</style>
