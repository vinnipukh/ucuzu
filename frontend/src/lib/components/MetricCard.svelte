<script lang="ts">
  type Tone = 'default' | 'positive' | 'negative' | 'accent';

  interface Props {
    label: string;
    value: string;
    hint?: string;
    tone?: Tone;
  }

  let { label, value, hint, tone = 'default' }: Props = $props();

  const toneColor = $derived(
    tone === 'positive'
      ? 'var(--color-positive)'
      : tone === 'negative'
        ? 'var(--color-destructive)'
        : tone === 'accent'
          ? 'var(--color-accent)'
          : 'var(--color-foreground)'
  );
</script>

<div class="metric" style={`--tone-color: ${toneColor}`}>
  <div class="metric-value">{value}</div>
  <div class="metric-label">{label}</div>
  {#if hint}<div class="metric-hint">{hint}</div>{/if}
</div>

<style>
  .metric {
    position: relative;
    display: flex;
    min-width: 0;
    min-height: 108px;
    flex-direction: column;
    gap: 5px;
    padding: 15px 16px 14px;
    border: 1px solid var(--color-border);
    border-radius: 15px;
    background: var(--color-card);
    box-shadow: var(--shadow-paper-small);
  }
  .metric::before {
    position: absolute;
    top: -1px;
    left: 14px;
    width: 34px;
    height: 3px;
    border-radius: 0 0 4px 4px;
    background: var(--tone-color);
    content: '';
  }
  .metric-value {
    overflow-wrap: anywhere;
    color: var(--tone-color);
    font-family: var(--font-mono);
    font-size: clamp(1.25rem, 2.3vw, 1.7rem);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.05em;
    line-height: 1.1;
  }
  .metric-label {
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    line-height: 1.35;
    text-transform: uppercase;
  }
  .metric-hint {
    color: var(--color-muted-foreground);
    font-size: 0.73rem;
    line-height: 1.4;
  }
</style>
