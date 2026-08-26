import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://alcaras.github.io',
  base: '/eu5ref/',
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});
