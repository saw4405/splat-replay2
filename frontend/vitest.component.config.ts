import { defineConfig, mergeConfig } from 'vitest/config';
import { baseVitestConfig } from './vitest.base.config';

export default mergeConfig(
  baseVitestConfig,
  defineConfig({
    test: {
      include: ['src/**/*.component.test.ts'],
    },
  })
);
