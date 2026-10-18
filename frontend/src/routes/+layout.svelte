<script lang="ts">
  import '../app.css';
  import favicon from '$lib/assets/favicon.svg';
  import { themeState, effectiveTheme } from '$lib/themes.svelte';

  let { children } = $props();

  // Apply the active color theme to the document root.
  $effect(() => {
    const root = document.documentElement;
    const dark = effectiveTheme() === 'dark';
    root.classList.toggle('dark', dark);
    root.style.colorScheme = dark ? 'dark' : 'light';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', dark ? '#171C23' : '#FFFFFF');
  });

  // Follow OS-level theme changes when in 'auto' mode.
  $effect(() => {
    if (themeState.mode !== 'auto' || typeof window === 'undefined') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => {
      const root = document.documentElement;
      const dark = media.matches;
      root.classList.toggle('dark', dark);
      root.style.colorScheme = dark ? 'dark' : 'light';
    };
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  });

  // Keep Svelte's effect graph aware of the theme variable.
  $effect(() => {
    void effectiveTheme();
  });
</script>

<svelte:head>
  <link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
