<script lang="ts">
  import { Settings } from 'lucide-svelte';
  import SettingsDialog from './components/settings/SettingsDialog.svelte';
  import VideoPreviewContainer from './components/recording/VideoPreviewContainer.svelte';
  import BottomDrawer from './components/recording/BottomDrawer.svelte';
  import AutoProcessNotification from './components/AutoProcessNotification.svelte';
  import { onMount } from 'svelte';
  import { api } from './api';
  import { subscribeDomainEvents } from './domainEvents';
  import { notifyRecordingStarted, notifyRecordingStopped } from './notification';
  import type {
    DomainEvent,
    AutoProcessPendingPayload,
    AutoSleepPendingPayload,
  } from './domainEvents';

  let isSettingsOpen = false;
  let autoProcessPayload: AutoProcessPendingPayload | null = null;
  let autoSleepPayload: AutoSleepPendingPayload | null = null;
  let bottomDrawerRef: BottomDrawer | null = null;

  function openSettings(): void {
    isSettingsOpen = true;
  }

  onMount(() => {
    const eventSource = subscribeDomainEvents((event: DomainEvent) => {
      if (event.type === 'domain.process.pending') {
        autoProcessPayload = event.payload as unknown as AutoProcessPendingPayload;
      } else if (event.type === 'domain.process.sleep.pending') {
        autoSleepPayload = event.payload as unknown as AutoSleepPendingPayload;
      } else if (event.type === 'domain.process.edit_upload_completed') {
        autoProcessPayload = null;
      } else if (event.type === 'domain.process.sleep.started') {
        autoSleepPayload = null;
      } else if (event.type === 'domain.process.started') {
        // 自動処理が実際に開始された
        autoProcessPayload = null;
        // BottomDrawerに進捗表示を促す
        if (bottomDrawerRef && typeof bottomDrawerRef.openProgress === 'function') {
          bottomDrawerRef.openProgress();
        }
      } else if (event.type === 'domain.recording.started') {
        // 録画開始時の通知
        notifyRecordingStarted();
      } else if (event.type === 'domain.recording.stopped') {
        // 録画終了時の通知
        notifyRecordingStopped();
      }
    });

    return () => {
      eventSource.close();
    };
  });
</script>

<main class="app-shell glass-surface">
  <div class="header">
    <div class="header-spacer"></div>
    <h1>Splat Replay</h1>
    <button
      class="icon-button settings-button"
      type="button"
      aria-label="Settings"
      on:click={openSettings}
      title="設定"
      data-testid="settings-button"
    >
      <Settings class="icon" aria-hidden="true" stroke-width={1.75} />
    </button>
  </div>

  <div class="preview-container">
    <VideoPreviewContainer />
  </div>

  <BottomDrawer bind:this={bottomDrawerRef} />

  <SettingsDialog bind:open={isSettingsOpen} />

  {#if autoProcessPayload}
    <AutoProcessNotification
      payload={autoProcessPayload}
      title="自動処理の開始予告"
      onStart={() => {
        if (bottomDrawerRef && typeof bottomDrawerRef.startAutoProcessing === 'function') {
          bottomDrawerRef.startAutoProcessing();
        }
      }}
      onDismiss={() => {
        autoProcessPayload = null;
      }}
    />
  {/if}

  {#if autoSleepPayload}
    <AutoProcessNotification
      payload={autoSleepPayload}
      title="スリープの開始予告"
      onStart={() => {
        return api.process.startSleep();
      }}
      onDismiss={() => {
        autoSleepPayload = null;
      }}
    />
  {/if}
</main>

<style>
  .app-shell {
    padding: 2rem;
    padding-bottom: 7rem; /* BottomDrawerのヘッダー分を確保 */
    max-width: 1400px;
    margin: 0 auto;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-sizing: border-box;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.5rem;
    flex-shrink: 0;
    position: relative;
  }

  .header-spacer {
    width: 2.5rem;
    flex-shrink: 0;
  }

  h1 {
    color: var(--accent-color);
    font-size: 3em;
    font-weight: 700;
    margin: 0;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    text-shadow:
      0 0 10px rgba(var(--theme-rgb-accent), 0.8),
      0 0 20px rgba(var(--theme-rgb-accent), 0.6),
      0 0 30px rgba(var(--theme-rgb-accent), 0.4),
      0 0 40px rgba(var(--theme-rgb-accent), 0.3),
      0 0 60px rgba(var(--theme-rgb-accent), 0.2),
      0 2px 4px rgba(var(--theme-rgb-black), 0.5);
    letter-spacing: 0.05em;
  }

  .preview-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 0;
    padding: 2rem 0 1rem 0;
    display: flex;
    justify-content: center;
  }

  .icon-button {
    height: 2.75rem;
    width: 2.75rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition:
      color 0.2s ease,
      border-color 0.2s ease,
      background 0.2s ease,
      box-shadow 0.2s ease;
  }

  .icon-button:focus-visible {
    outline: none;
  }

  .settings-button {
    border-radius: 50%;
    border: 1px solid rgba(var(--theme-rgb-white), 0.08);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-surface-card), 0.4) 0%,
      rgba(var(--theme-rgb-surface-card-dark), 0.26) 100%
    );
    box-shadow: 0 5px 14px rgba(var(--theme-rgb-black), 0.16);
    backdrop-filter: blur(6px) saturate(130%);
    -webkit-backdrop-filter: blur(6px) saturate(130%);
  }

  .settings-button:hover {
    border-color: rgba(var(--theme-rgb-white), 0.14);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.1) 0%,
      rgba(var(--theme-rgb-white), 0.04) 100%
    );
    box-shadow:
      0 8px 18px rgba(var(--theme-rgb-black), 0.2),
      0 0 8px rgba(var(--theme-rgb-accent), 0.12);
  }

  .settings-button:active {
    box-shadow: 0 4px 10px rgba(var(--theme-rgb-black), 0.18);
  }
</style>
