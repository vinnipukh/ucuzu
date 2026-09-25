import { effectiveTheme } from '$lib/themes.svelte';

export interface ChartTheme {
  dark: boolean;
  text: string;
  axisLine: string;
  splitLine: string;
  tooltipBg: string;
  tooltipText: string;
  border: string;
  /** Paper-and-ink categorical palette with a warm accent for emphasis. */
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
        text: '#d6cec1',
        axisLine: '#6f675c',
        splitLine: '#37332d',
        tooltipBg: '#25221e',
        tooltipText: '#f7f2e8',
        border: '#5c554b',
        palette: ['#f5efe3', '#fb923c', '#5eead4', '#c4b5fd', '#cbd5e1', '#fbbf24', '#93c5fd', '#fda4af']
      }
    : {
        dark,
        text: '#57534e',
        axisLine: '#aaa296',
        splitLine: '#e5ded2',
        tooltipBg: '#fffdf8',
        tooltipText: '#26231f',
        border: '#c9c0b4',
        palette: ['#1f2937', '#c2410c', '#0f766e', '#7c3aed', '#64748b', '#b45309', '#2563eb', '#9f1239']
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
    textStyle: { color: theme.text, fontFamily: "'Fira Sans', system-ui, sans-serif" },
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
