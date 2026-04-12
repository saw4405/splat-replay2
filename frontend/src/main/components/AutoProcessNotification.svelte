<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import { Clock } from 'lucide-svelte';
  import type { AutoProcessPendingPayload, AutoSleepPendingPayload } from '../domainEvents';
  import { UI_COUNTDOWN_TICK_INTERVAL_MS } from '../renderMode';

  type CountdownPayload = AutoProcessPendingPayload | AutoSleepPendingPayload;

  interface Props {
    payload: CountdownPayload;
    title?: string;
    onDismiss: () => void;
    onStart: () => void | Promise<void>;
  }

  let { payload, title = '自動処理の開始予告', onDismiss, onStart }: Props = $props();

  // マウント時の初期値のみ使用（カウントダウン中に payload は変化しない）
  let remainingSeconds = $state(untrack(() => payload.timeout_seconds));
  let progress = $state(100);
  let intervalId: number;
  let startRequested = $state(false);
  const totalSeconds = $derived(payload.timeout_seconds);

  async function handleStart() {
    if (startRequested) {
      return;
    }
    startRequested = true;
    if (intervalId) {
      clearInterval(intervalId);
    }
    onDismiss();
    try {
      await onStart();
    } catch (error) {
      console.error('開始に失敗しました:', error);
    }
  }

  function handleCancel(): void {
    if (startRequested) {
      return;
    }
    startRequested = true;
    if (intervalId) {
      clearInterval(intervalId);
    }
    onDismiss();
  }

  onMount(() => {
    const startTime = Date.now();
    const endTime = startTime + totalSeconds * 1000;

    intervalId = window.setInterval(() => {
      const now = Date.now();
      const left = Math.max(0, endTime - now);
      remainingSeconds = Math.ceil(left / 1000);
      progress = (left / (totalSeconds * 1000)) * 100;

      if (left <= 0) {
        clearInterval(intervalId);
        void handleStart();
      }
    }, UI_COUNTDOWN_TICK_INTERVAL_MS);
  });

  onDestroy(() => {
    if (intervalId) clearInterval(intervalId);
  });
</script>

<div class="notification-card" role="alert">
  <div class="content">
    <div class="header">
      <Clock size={16} class="icon-pulse" color="var(--accent-color)" />
      <h3 class="title">{title}</h3>
    </div>

    <p class="message">{payload.message}</p>

    <div class="action-row">
      <span class="timer">あと {remainingSeconds} 秒</span>
      <button class="cancel-button" onclick={handleCancel} disabled={startRequested}>
        キャンセル
      </button>
    </div>
  </div>

  <div class="progress-container">
    <div class="progress-bar" style="width: {progress}%"></div>
  </div>
</div>

<style>
  .notification-card {
    position: fixed;
    top: 24px;
    left: 24px;
    width: 380px;
    background: rgba(var(--theme-rgb-space), 0.95);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
    border-radius: 12px;
    box-shadow: 0 6px 20px rgba(var(--theme-rgb-black), 0.36);
    z-index: 9999;
    overflow: hidden;
    animation: slide-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    font-family: inherit;
  }

  .content {
    padding: 16px;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--theme-color-white);
    margin: 0;
  }

  .message {
    font-size: 0.85rem;
    color: rgba(var(--theme-rgb-white), 0.8);
    margin: 0 0 16px 0;
    line-height: 1.5;
  }

  .action-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .timer {
    font-size: 0.85rem;
    color: var(--accent-color);
    font-feature-settings: 'tnum';
    font-variant-numeric: tabular-nums;
  }

  .cancel-button {
    background: rgba(var(--theme-rgb-white), 0.1);
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
    color: var(--theme-color-white);
    font-size: 0.85rem;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .cancel-button:hover {
    background: rgba(var(--theme-rgb-white), 0.15);
    border-color: rgba(var(--theme-rgb-white), 0.2);
  }

  .progress-container {
    height: 3px;
    background: rgba(var(--theme-rgb-white), 0.1);
    width: 100%;
  }

  .progress-bar {
    height: 100%;
    background: var(--accent-color);
    transition: width 0.1s linear;
    box-shadow: 0 0 4px rgba(var(--theme-rgb-accent), 0.25);
  }

  :global(.icon-pulse) {
    opacity: 0.9;
  }

  @keyframes slide-in {
    from {
      opacity: 0;
      transform: translateY(-20px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>
