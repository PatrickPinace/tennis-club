import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  integrations: [tailwind()],

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
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
