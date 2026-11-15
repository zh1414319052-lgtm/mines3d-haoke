import { defineConfig } from 'vite';
export default defineConfig({ server: { port: 5178, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8768', '/ws': { target: 'ws://127.0.0.1:8768', ws: true } } }, build: { outDir: 'dist', emptyOutDir: false }, esbuild: { jsx: 'automatic' } });
