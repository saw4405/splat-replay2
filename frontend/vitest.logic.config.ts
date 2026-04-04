import { defineConfig, mergeConfig } from 'vitest/config';
import { baseVitestConfig } from './vitest.base.config';

export default mergeConfig(
  baseVitestConfig,
  defineConfig({
    test: {
      include: ['src/**/*.test.ts'],
      exclude: ['src/**/*.component.test.ts', 'src/**/*.integration.test.ts'],
    },
  })
);
