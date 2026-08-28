import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/postcss';
import path from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  css: { postcss: { plugins: [tailwindcss()] } },
  resolve: { alias: { '@': path.resolve(__dirname, '.') } },
  server: { port: 9000, proxy: { '/api': 'http://127.0.0.1:9001' } },
  build: { outDir: 'dist/spa', emptyOutDir: true },
});
