import { effectiveTheme } from '$lib/themes.svelte';

/** Colours for ECharts options in the current light or dark theme. */
export interface ChartTheme {
  dark: boolean;
  text: string;
  axisLine: string;
  splitLine: string;
  tooltipBg: string;
  tooltipText: string;
  border: string;
  /** Categorical palette led by the blue accent. */
  palette: string[];
}

/**
 * Current chart theme. Reads the effective color theme, so calling this inside
 * a component (derived/effect) keeps charts reactive to theme changes.
 */
export function getChartTheme(): ChartTheme {
  const dark = effectiveTheme() === 'dark';
  return dark
    ? {
        dark,
        text: '#a3adbb',
        axisLine: '#39414d',
        splitLine: '#232a33',
        tooltipBg: '#171c23',
        tooltipText: '#e8edf3',
        border: '#2a313b',
        palette: ['#5b9df0', '#f59e0b', '#4cc38a', '#c084fc', '#f472b6', '#22d3ee', '#a3adbb', '#fb7185']
      }
    : {
        dark,
        text: '#5f6b7a',
        axisLine: '#c4cbd4',
        splitLine: '#eef1f5',
        tooltipBg: '#ffffff',
        tooltipText: '#1d2530',
        border: '#e1e5eb',
        palette: ['#1468d6', '#f59e0b', '#0f8a4c', '#7c3aed', '#db2777', '#0891b2', '#5f6b7a', '#c62828']
      };
}

/** Base grid/tooltip/axis options shared by all charts. */
export function baseChartOption(theme: ChartTheme) {
  return {
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: theme.tooltipBg,
      borderColor: theme.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: theme.tooltipText, fontSize: 12 },
      confine: true
    },
    textStyle: { color: theme.text, fontFamily: "'Inter', system-ui, sans-serif" },
    axisPointer: { lineStyle: { color: theme.splitLine } },
    valueAxis: {
      axisLabel: { color: theme.text, fontSize: 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: theme.splitLine, width: 1 } }
    },
    categoryAxis: {
      axisLabel: { color: theme.text, fontSize: 11 },
      axisLine: { lineStyle: { color: theme.axisLine, width: 1 } },
      axisTick: { show: false }
    }
  };
}
