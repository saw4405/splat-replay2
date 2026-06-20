import { defineConfig, mergeConfig } from 'vitest/config';
import { baseVitestConfig } from './vitest.base.config';

export default mergeConfig(
  baseVitestConfig,
  defineConfig({
    test: {
      include: [
        'src/**/*.{test,component.test,integration.test}.ts',
        'tests/infra/**/*.test.ts',
      ],
    },
  })
);
