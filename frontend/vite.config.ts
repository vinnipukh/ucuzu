import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import staticAdapter from '@sveltejs/adapter-static';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Pure client-side SPA: the Falcon API is a separate process, so the
			// frontend is a static bundle. It calls same-origin /api by default;
			// set VITE_API_BASE_URL at build time for an API on another origin.
			adapter: staticAdapter({ fallback: 'index.html' })
		})
	],
	server: {
		// `npm run dev` only (not `vite preview` or the static build): forwards the
		// SPA's same-origin /api calls (empty VITE_API_BASE_URL, the default) to
		// the Falcon API on :8000.
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});
