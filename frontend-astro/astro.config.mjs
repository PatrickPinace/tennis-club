import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import react from '@astrojs/react';
import node from '@astrojs/node';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// https://astro.build/config
export default defineConfig({
  integrations: [tailwind(), react()],
  devToolbar: {
    enabled: false
  },

  // Prefiks URL dla wdrożenia równoległego obok Django pod /astro/.
  // W dev zostaw jako '/' (domyślne) — lokalnie Astro działa bez prefiksu.
  // W produkcji (docker build) ustaw ASTRO_BASE=/astro w env lub zmień tu na '/astro'.
  // Wartość trafia do import.meta.env.BASE_URL i jest używana przez src/lib/url.ts.
  base: process.env.ASTRO_BASE ?? '/',

  // Tryb hybrid: większość stron renderowana statycznie przy buildzie,
  // ale strony oznaczone export const prerender = false są SSR (mają dostęp do cookies).
  // Wymagany do działania Astro.request.headers (np. cookie sesji Django) w produkcji.
  output: 'hybrid',
  adapter: node({
    mode: 'standalone',
  }),

  // Dev proxy: przekazuje /api/* do Django :8000 — dzięki temu cookie sessionid
  // jest ustawiane na tym samym origin co Astro (:4321) i middleware widzi sesję.
  vite: {
    resolve: {
      alias: {
        // Alias @/ → src/ — Astro 4 nie zawsze czyta paths z tsconfig.json w trybie SSR dev.
        // Jawna definicja tu jest niezawodna i nie wymaga vite-tsconfig-paths.
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      hmr: {
        path: '/_astro/hmr',
      },
      watch: {
        // Wymusza aktywne sprawdzanie zmian (polling) - kluczowe dla Docker na Windows
        usePolling: true,
        interval: 100,
      },
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
