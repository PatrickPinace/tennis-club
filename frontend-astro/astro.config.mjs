import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  integrations: [tailwind()],
  // W trybie dev proxy do Django API (uruchomionego na :8000)
  // Odkomentuj gdy Django API jest dostępne:
  // server: {
  //   proxy: {
  //     '/api': 'http://localhost:8000',
  //   }
  // },
  output: 'static',
});
