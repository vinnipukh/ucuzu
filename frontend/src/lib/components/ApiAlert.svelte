<script lang="ts">
  interface Props {
    message: string;
    errorMeta?: Record<string, unknown> | null;
    role?: 'error' | 'warning';
  }
  let { message, errorMeta = null, role = 'error' }: Props = $props();
</script>

<div class="alert" class:warning={role === 'warning'} role={role === 'error' ? 'alert' : undefined}>
  <div class="alert-body">
    {#if role === 'warning'}
      <svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><path d="M12 9v4M12 17h.01" /></svg>
    {:else}
      <svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" /></svg>
    {/if}
    <span>{message}</span>
  </div>
  {#if errorMeta && Object.keys(errorMeta).length > 0}
    <details class="meta-details">
      <summary>API metadata</summary>
      <pre>{JSON.stringify(errorMeta, null, 2)}</pre>
    </details>
  {/if}
</div>

<style>
  .alert {
    display: flex;
    flex-direction: column;
    gap: 7px;
    padding: 12px 14px;
    border: 1px solid var(--color-border);
    border-left: 4px solid var(--color-destructive);
    border-radius: 13px;
    background: var(--color-card);
    color: var(--color-destructive);
    font-size: 0.86rem;
  }
  .alert.warning {
    border-left-color: var(--color-accent);
    color: var(--color-accent);
  }
  .alert-body {
    display: flex;
    align-items: baseline;
    gap: 9px;
  }
  .icon {
    flex: none;
    transform: translateY(1px);
  }
  .meta-details summary {
    cursor: pointer;
    font-size: 0.76rem;
    opacity: 0.8;
  }
  .meta-details pre {
    max-height: 200px;
    margin: 7px 0 0;
    padding: 10px;
    overflow: auto;
    border: 1px solid var(--color-border);
    border-radius: 9px;
    background: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 0.72rem;
  }
</style>
