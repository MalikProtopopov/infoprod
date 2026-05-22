import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './'),
    },
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./__tests__/setup.ts'],
    globals: true,
    css: false,
    pool: 'threads',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov', 'json-summary'],
      include: ['app/**', 'lib/**', 'components/**'],
      exclude: [
        '**/*.config.{ts,mjs,js}',
        '__tests__/**',
        '.next/**',
        'node_modules/**',
        '**/layout.tsx',
      ],
      thresholds: {
        // В Phase 1 пока 0 — поднимем до 98% в Phase 5
        lines: 0,
        functions: 0,
        branches: 0,
        statements: 0,
      },
    },
  },
});
