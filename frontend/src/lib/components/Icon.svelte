<script lang="ts">
  /** Small stroke icons (24px grid) used by the shop pages. */
  type Name = 'search' | 'bell' | 'menu' | 'tag' | 'chart' | 'arrow-down' | 'arrow-right' | 'store' | 'x' | 'sun' | 'moon' | 'trend';

  let { name, size = 20 }: { name: Name; size?: number } = $props();

  const paths: Record<Name, string> = {
    search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4.2-4.2',
    bell: 'M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0',
    menu: 'M4 7h16M4 12h16M4 17h16',
    tag: 'M3 12V4h8l9 9-8 8zM7.5 7.5h.01',
    chart: 'M4 20V4M4 20h16M8 16l4-5 3 3 5-6',
    'arrow-down': 'M12 5v14M6 13l6 6 6-6',
    'arrow-right': 'M5 12h14M13 6l6 6-6 6',
    store: 'M4 10v10h16V10M3 10l2-6h14l2 6zM9 20v-6h6v6',
    x: 'M6 6l12 12M18 6L6 18',
    sun: 'M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
    moon: 'M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z',
    trend: 'M3 17l6-6 4 4 8-8M15 7h6v6'
  };
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  <path d={paths[name]} />
</svg>
