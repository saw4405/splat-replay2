import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  // Consult https://svelte.dev/docs#compile-time-svelte-preprocess
  // for more information about preprocessors
  preprocess: vitePreprocess(),
  compilerOptions: {
    // Preserve unused CSS for future use
  },
  onwarn: (warning, handler) => {
    // Ignore css-unused-selector and a11y-no-static-element-interactions warnings
    if (
      warning.code === 'css-unused-selector' ||
      warning.code === 'a11y-no-static-element-interactions'
    )
      return;
    handler(warning);
  },
};
