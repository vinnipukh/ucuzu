/** Colour theme mode; `auto` follows the OS `prefers-color-scheme`. */
export type Theme = 'auto' | 'light' | 'dark';

const STORAGE_KEY = 'inflation-dashboard-theme';

function initialTheme(): Theme {
  if (typeof localStorage === 'undefined') return 'auto';
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'auto' ? stored : 'auto';
}

/** Reactive theme state; `mode` starts from localStorage (`inflation-dashboard-theme`), else `auto`. */
export const themeState = $state({ mode: initialTheme() as Theme });

/** The theme actually shown: `mode`, or the OS preference when `mode` is `auto`. */
export function effectiveTheme(): 'light' | 'dark' {
  const mode = themeState.mode;
  if (mode === 'light' || mode === 'dark') return mode;
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return 'light';
}

/** Set the theme mode and remember it in localStorage. */
export function setTheme(next: Theme): void {
  themeState.mode = next;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, next);
  }
}

/** Switch to the opposite of the currently shown theme (light <-> dark); never returns to `auto`. */
export function toggleTheme(): void {
  setTheme(effectiveTheme() === 'dark' ? 'light' : 'dark');
}
