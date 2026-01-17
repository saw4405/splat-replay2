<script lang="ts">
  import { Settings } from 'lucide-svelte';
  import SettingsDialog from './components/settings/SettingsDialog.svelte';
  import VideoPreviewContainer from './components/recording/VideoPreviewContainer.svelte';
  import BottomDrawer from './components/recording/BottomDrawer.svelte';
  import AutoProcessNotification from './components/AutoProcessNotification.svelte';
  import { onMount } from 'svelte';
  import { api } from './api';
  import { subscribeDomainEvents } from './domainEvents';
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
    color: #19d3c7;
    font-size: 3em;
    font-weight: 700;
    margin: 0;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    text-shadow:
      0 0 10px rgba(25, 211, 199, 0.8),
      0 0 20px rgba(25, 211, 199, 0.6),
      0 0 30px rgba(25, 211, 199, 0.4),
      0 0 40px rgba(25, 211, 199, 0.3),
      0 0 60px rgba(25, 211, 199, 0.2),
      0 2px 4px rgba(0, 0, 0, 0.5);
    letter-spacing: 0.05em;
    animation: pulse-glow 3s ease-in-out infinite;
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

  @keyframes pulse-glow {
    0%,
    100% {
      text-shadow:
        0 0 10px rgba(25, 211, 199, 0.8),
        0 0 20px rgba(25, 211, 199, 0.6),
        0 0 30px rgba(25, 211, 199, 0.4),
        0 0 40px rgba(25, 211, 199, 0.3),
        0 0 60px rgba(25, 211, 199, 0.2),
        0 2px 4px rgba(0, 0, 0, 0.5);
    }
    50% {
      text-shadow:
        0 0 15px rgba(25, 211, 199, 1),
        0 0 30px rgba(25, 211, 199, 0.8),
        0 0 45px rgba(25, 211, 199, 0.6),
        0 0 60px rgba(25, 211, 199, 0.4),
        0 0 90px rgba(25, 211, 199, 0.3),
        0 2px 4px rgba(0, 0, 0, 0.5);
    }
  }

  .icon-button {
    height: 2.75rem;
    width: 2.75rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .icon-button:hover {
    transform: translateY(-2px);
  }

  .icon-button:focus-visible {
    outline: none;
  }

  .icon-button:active {
    transform: translateY(0);
  }

  .settings-button {
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.05) 0%,
      rgba(255, 255, 255, 0.01) 100%
    );
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
  }

  .settings-button:hover {
    border-color: rgba(255, 255, 255, 0.14);
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.08) 0%,
      rgba(255, 255, 255, 0.02) 100%
    );
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
  }

  .settings-button:active {
    transform: translateY(0);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }
</style>
