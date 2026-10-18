<script lang="ts">
  import { themeState, effectiveTheme, toggleTheme } from '$lib/themes.svelte';

  interface Props {
    connected: boolean | null;
    checking: boolean;
    onRetry: () => void;
  }
  let { connected, checking, onRetry }: Props = $props();

  let themeLabel = $derived(themeState.mode === 'auto' ? 'Auto' : themeState.mode === 'dark' ? 'Dark' : 'Light');
</script>

<header class="header paper-panel">
  <div class="brand">
    <div class="brand-mark" aria-hidden="true">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 18.5 9 13l3.5 3.5L20 8" />
        <path d="M15 8h5v5" />
        <path d="M4 21h16" />
      </svg>
    </div>
    <div>
      <p class="paper-kicker"><a href="/">← ucuzu</a> · market research / 01</p>
      <h1 class="wordmark">Inflation Study</h1>
      <p class="subtitle">Price tracking across Turkish retailers — Falcon API</p>
    </div>
  </div>

  <div class="header-index" aria-label="Dashboard data scope">
    <span class="index-label">search engine</span>
    <span class="index-value">product / retailer / category</span>
  </div>

  <div class="actions">
    <div class="status">
      {#if checking}
        <span class="dot checking" aria-hidden="true"></span>
        <span class="status-text">Checking API…</span>
      {:else if connected === true}
        <span class="dot ok" aria-hidden="true"></span>
        <span class="status-text">API connected</span>
      {:else if connected === false}
        <span class="dot bad" aria-hidden="true"></span>
        <button type="button" class="retry" onclick={onRetry}>API unreachable — retry</button>
      {:else}
        <span class="dot" aria-hidden="true"></span>
        <span class="status-text">Not checked</span>
      {/if}
    </div>

    <button type="button" class="theme-toggle" onclick={toggleTheme} aria-label="Toggle color theme">
      {#if effectiveTheme() === 'dark'}
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
      {:else}
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      {/if}
      <span class="theme-name">{themeLabel}</span>
    </button>
  </div>
</header>

<style>
  .header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 24px;
    margin-bottom: 20px;
    padding: 18px 20px;
  }
  .brand {
    display: flex;
    align-items: center;
    min-width: 0;
    gap: 13px;
  }
  .brand-mark {
    display: grid;
    flex: none;
    width: 44px;
    height: 44px;
    place-items: center;
    border: 1px solid var(--color-line);
    border-radius: 14px;
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }
  .wordmark {
    margin: 4px 0 0;
    font-size: clamp(1.1rem, 2vw, 1.45rem);
    font-weight: 700;
    letter-spacing: -0.05em;
  }
  .subtitle {
    margin: 4px 0 0;
    color: var(--color-muted-foreground);
    font-size: 0.8rem;
  }
  .header-index {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 190px;
    padding: 9px 13px;
    border: 1px solid var(--color-border);
    border-radius: 12px;
    background: var(--color-muted);
  }
  .index-label {
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-size: 0.63rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .index-value {
    color: var(--color-foreground);
    font-family: var(--font-mono);
    font-size: 0.73rem;
  }
  .actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
    flex-wrap: wrap;
  }
  .status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 34px;
    padding: 7px 10px;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    color: var(--color-muted-foreground);
    font-size: 0.76rem;
    font-variant-numeric: tabular-nums;
  }
  .dot {
    width: 7px;
    height: 7px;
    flex: none;
    border-radius: 50%;
    background: var(--color-muted-foreground);
  }
  .dot.ok {
    background: var(--color-positive);
  }
  .dot.bad {
    background: var(--color-destructive);
  }
  .dot.checking {
    background: var(--color-accent);
    animation: pulse 1s ease-in-out infinite;
  }
  @keyframes pulse {
    50% {
      opacity: 0.3;
    }
  }
  .retry {
    padding: 0;
    border: 0;
    background: none;
    color: var(--color-destructive);
    cursor: pointer;
    font-family: inherit;
    font-size: 0.76rem;
    font-weight: 600;
  }
  .retry:hover {
    text-decoration: underline;
  }
  .theme-toggle {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 34px;
    padding: 7px 10px;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-card);
    color: var(--color-muted-foreground);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    transition: border-color 160ms ease, color 160ms ease, transform 160ms ease;
  }
  .theme-toggle:hover {
    border-color: var(--color-line);
    color: var(--color-foreground);
    transform: translateY(-1px);
  }
  @media (max-width: 980px) {
    .header {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .header-index {
      grid-column: 1 / -1;
      grid-row: 2;
      width: fit-content;
    }
  }
  @media (max-width: 620px) {
    .header {
      grid-template-columns: 1fr;
      gap: 14px;
      padding: 16px;
    }
    .header-index {
      grid-column: auto;
      grid-row: auto;
      width: 100%;
    }
    .actions {
      justify-content: flex-start;
    }
  }
</style>
