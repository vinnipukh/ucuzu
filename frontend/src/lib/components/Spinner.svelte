<script lang="ts">
  interface Props {
    label?: string;
    inline?: boolean;
  }
  let { label = 'Loading…', inline = false }: Props = $props();
</script>

<div class="spinner-wrap" class:inline>
  <span class="spinner" aria-hidden="true"></span>
  <span class="label">{label}</span>
</div>

<style>
  .spinner-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    min-height: 110px;
    padding: 28px 0;
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-size: 0.76rem;
  }
  .spinner-wrap.inline {
    min-height: 0;
    justify-content: flex-start;
    padding: 8px 0;
  }
  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--color-border);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation-duration: 2.5s;
    }
  }
</style>
