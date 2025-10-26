import './app.css'
import App from './App.svelte'

console.log('Splat Replay: Starting application...');
console.log('Target element:', document.getElementById('app'));

const app = new App({
  target: document.getElementById('app')!,
})

console.log('Splat Replay: Application initialized!', app);

export default app
