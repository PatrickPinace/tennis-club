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
});
