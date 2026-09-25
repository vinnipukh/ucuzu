<script lang="ts">
  import SearchableMultiSelect from '$lib/components/SearchableMultiSelect.svelte';
  import ApiAlert from '$lib/components/ApiAlert.svelte';
  import { filters, buildQueryMap } from '$lib/stores/filters.svelte';
  import { API_BASE_URL } from '$lib/api/client';

  interface Props {
    onApplyApiUrl: (url: string) => void;
    inventoryWarnings: string[];
  }
  let { onApplyApiUrl, inventoryWarnings }: Props = $props();

  let urlDraft = $state(filters.apiBaseUrl);

  // Local drafts for inputs; apply on change so the UI stays responsive.
  let startDraft = $state(filters.startDate);
  let endDraft = $state(filters.endDate);
  let maxFilesDraft = $state(filters.maxFiles);
  let allHistoryDraft = $state(filters.allHistory);

  $effect(() => {
    startDraft = filters.startDate;
  });
  $effect(() => {
    endDraft = filters.endDate;
  });
  $effect(() => {
    maxFilesDraft = filters.maxFiles;
  });
  $effect(() => {
    allHistoryDraft = filters.allHistory;
  });

  let queryCount = $derived(Object.keys(buildQueryMap()).length);

  function applyStart(): void {
    if (startDraft !== filters.startDate) filters.startDate = startDraft;
  }
  function applyEnd(): void {
    if (endDraft !== filters.endDate) filters.endDate = endDraft;
  }
  function applyMaxFiles(): void {
    if (maxFilesDraft !== filters.maxFiles) filters.maxFiles = maxFilesDraft;
  }
  function applyAllHistory(): void {
    if (allHistoryDraft !== filters.allHistory) filters.allHistory = allHistoryDraft;
  }
</script>



<aside class="sidebar" aria-label="Dashboard settings">
  <div class="sidebar-intro">
    <p class="paper-kicker">control panel</p>
    <p>Shape the dataset before opening a view.</p>
  </div>

  <section class="section">
    <div class="section-heading">
      <span class="section-number">01</span>
      <h2 class="section-title">API settings</h2>
    </div>
    <div class="field">
      <label class="field-label" for="api-url">Falcon API base URL</label>
      <div class="url-row">
        <input
          id="api-url"
          type="text"
          bind:value={urlDraft}
          spellcheck="false"
          placeholder="http://localhost:8000"
        />
        <button
          type="button"
          class="apply"
          onclick={() => onApplyApiUrl(urlDraft.trim() || 'http://localhost:8000')}
          disabled={urlDraft.trim() === filters.apiBaseUrl}
        >
          Apply
        </button>
      </div>
      {#if filters.apiBaseUrl !== API_BASE_URL}
        <p class="hint">Build default: {API_BASE_URL}</p>
      {/if}
    </div>

    {#if inventoryWarnings.length > 0}
      <div class="warnings">
        {#each inventoryWarnings as warning (warning)}
          <ApiAlert message={warning} role="warning" />
        {/each}
      </div>
    {/if}

    {#if filters.inventoryReady}
      <dl class="inventory-meta">
        <div><dt>Inventory files</dt><dd>{filters.inventoryFileCount?.toLocaleString('tr-TR') ?? '-'}</dd></div>
        <div><dt>Earliest date</dt><dd>{filters.inventoryMinDate?.slice(0, 10) ?? '-'}</dd></div>
        <div><dt>Latest date</dt><dd>{filters.inventoryMaxDate?.slice(0, 10) ?? '-'}</dd></div>
      </dl>
    {/if}
  </section>

  {#if filters.inventoryReady}
    <section class="section">
      <div class="section-heading">
        <span class="section-number">02</span>
        <h2 class="section-title">Load settings</h2>
      </div>

      <SearchableMultiSelect
        label="Retailers to load"
        options={filters.retailerOptions}
        value={filters.selectedRetailers}
        placeholder="Type a few letters; misspellings are okay"
        help="Loading fewer retailers is much faster. Add the large datasets only when needed."
        onChange={(next) => { filters.selectedRetailers.length = 0; filters.selectedRetailers.push(...next); }}
      />

      <div class="dates">
        <div class="field">
          <label class="field-label" for="start-date">Start date</label>
          <input
            id="start-date"
            type="date"
            min={filters.inventoryMinDate?.slice(0, 10) ?? undefined}
            max={filters.inventoryMaxDate?.slice(0, 10) ?? undefined}
            value={startDraft ?? ''}
            onchange={applyStart}
          />
        </div>
        <div class="field">
          <label class="field-label" for="end-date">End date</label>
          <input
            id="end-date"
            type="date"
            min={filters.inventoryMinDate?.slice(0, 10) ?? undefined}
            max={filters.inventoryMaxDate?.slice(0, 10) ?? undefined}
            value={endDraft ?? ''}
            onchange={applyEnd}
          />
        </div>
      </div>

      <div class="field">
        <label class="field-label" for="max-files">
          Max CSV files per retailer: <strong class="value">{maxFilesDraft}</strong>
        </label>
        <input
          id="max-files"
          type="range"
          min="10"
          max="160"
          step="5"
          value={maxFilesDraft}
          oninput={(event) => {
            maxFilesDraft = Number((event.currentTarget as HTMLInputElement).value);
            applyMaxFiles();
          }}
          disabled={allHistoryDraft}
        />
        <p class="hint">Uses the newest files in the selected date range. Raise this for deeper history; lower it for faster loading.</p>
      </div>

      <label class="checkbox">
        <input type="checkbox" checked={allHistoryDraft} onchange={applyAllHistory} />
        <span>Load all files in date range</span>
      </label>
      {#if allHistoryDraft}
        <p class="hint warn">All-history mode sends all_history=true and max_files=0 to the API.</p>
      {/if}
    </section>

    <footer class="sidebar-footer">
      <p>Prepared {queryCount} common query parameter{queryCount === 1 ? '' : 's'} for data endpoints.</p>
    </footer>
  {/if}
</aside>

<style>
  .sidebar {
    position: sticky;
    top: 20px;
    display: flex;
    flex-direction: column;
    min-width: 0;
    gap: 16px;
    padding: 18px;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-panel);
    background: var(--color-card);
    box-shadow: var(--shadow-paper);
  }
  .sidebar-intro {
    display: flex;
    flex-direction: column;
    gap: 7px;
    padding-bottom: 15px;
    border-bottom: 1px solid var(--color-border);
  }
  .sidebar-intro p:last-child {
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.82rem;
    line-height: 1.45;
  }
  .section {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding-top: 2px;
  }
  .section + .section {
    padding-top: 16px;
    border-top: 1px solid var(--color-border);
  }
  .section-heading {
    display: flex;
    align-items: center;
    gap: 9px;
  }
  .section-number {
    display: grid;
    width: 24px;
    height: 24px;
    place-items: center;
    border: 1px solid var(--color-line);
    border-radius: 8px;
    color: var(--color-accent);
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
  }
  .section-title {
    margin: 0;
    color: var(--color-foreground);
    font-family: var(--font-mono);
    font-size: 0.73rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .field-label {
    color: var(--color-foreground);
    font-size: 0.8rem;
    font-weight: 600;
  }
  .url-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  input[type='text'],
  input[type='date'] {
    width: 100%;
    box-sizing: border-box;
    min-width: 0;
    padding: 9px 10px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    background: var(--color-background);
    color: var(--color-card-foreground);
    font-family: var(--font-mono);
    font-size: 0.76rem;
    font-variant-numeric: tabular-nums;
    transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
  }
  input[type='text']:hover,
  input[type='date']:hover {
    border-color: var(--color-line);
  }
  input[type='text']:focus,
  input[type='date']:focus {
    border-color: var(--color-accent);
    outline: none;
    box-shadow: 0 0 0 3px var(--color-accent-soft);
  }
  .apply {
    flex: none;
    padding: 9px 11px;
    border: 1px solid var(--color-line);
    border-radius: 10px;
    background: var(--color-primary);
    color: var(--color-on-primary);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    transition: transform 160ms ease, opacity 160ms ease;
  }
  .apply:disabled {
    cursor: default;
    opacity: 0.35;
  }
  .apply:not(:disabled):hover {
    transform: translateY(-1px);
  }
  .hint {
    margin: 0;
    color: var(--color-muted-foreground);
    font-size: 0.73rem;
    line-height: 1.45;
  }
  .hint.warn {
    color: var(--color-accent);
  }
  .warnings {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .inventory-meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin: 0;
    padding: 10px;
    border: 1px solid var(--color-border);
    border-radius: 12px;
    background: var(--color-muted);
  }
  .inventory-meta div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .inventory-meta dt {
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-size: 0.61rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .inventory-meta dd {
    margin: 0;
    overflow: hidden;
    color: var(--color-foreground);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .dates {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  input[type='range'] {
    width: 100%;
    accent-color: var(--color-accent);
    cursor: pointer;
  }
  .value {
    color: var(--color-foreground);
    font-family: var(--font-mono);
  }
  .checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--color-card-foreground);
    cursor: pointer;
    font-size: 0.8rem;
  }
  .checkbox input {
    width: 15px;
    height: 15px;
    accent-color: var(--color-accent);
    cursor: pointer;
  }
  .sidebar-footer {
    padding-top: 14px;
    border-top: 1px solid var(--color-border);
    color: var(--color-muted-foreground);
    font-size: 0.72rem;
  }
  .sidebar-footer p {
    margin: 0;
  }
  @media (max-width: 1024px) {
    .sidebar {
      position: static;
    }
  }
  @media (max-width: 420px) {
    .dates {
      grid-template-columns: 1fr;
    }
  }
</style>
