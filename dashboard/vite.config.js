import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
        eda1: 'eda1.html',
        eda2: 'eda2.html',
        eda3: 'eda3.html',
      }
    }
  }
});
