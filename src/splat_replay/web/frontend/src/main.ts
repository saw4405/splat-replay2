import App from './App.svelte';

const target = document.getElementById('app');

if (!target) {
  throw new Error('ルート要素 #app が見つかりません。');
}

const app = new App({
  target
});

export default app;
