import './app.css';
import { flushSync, mount } from 'svelte';
import App from './App.svelte';

console.log('Splat Replay: Starting application...');
console.log('Target element:', document.getElementById('app'));

const target = document.getElementById('app');
if (!target) {
  throw new Error('App target element was not found');
}

const app = mount(App, {
  target,
});
flushSync();

console.log('Splat Replay: Application initialized!', app);

export default app;
