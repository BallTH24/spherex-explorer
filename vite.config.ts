import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Standalone demo only. The module itself is plain source and needs no build step.
export default defineConfig({
  root: 'demo',
  plugins: [react()],
  build: { outDir: '../dist-demo', emptyOutDir: true },
});
