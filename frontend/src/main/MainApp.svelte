<script lang="ts">
  import { Settings, PanelBottom } from 'lucide-svelte';
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

  let isSettingsOpen = $state(false);
  let autoProcessPayload = $state<AutoProcessPendingPayload | null>(null);
  let autoSleepPayload = $state<AutoSleepPendingPayload | null>(null);
  let bottomDrawerRef = $state<BottomDrawer | null>(null);
  let recordedDataCount = $state(0);
  const drawerButtonLabel = $derived(
    recordedDataCount > 0 ? `データ一覧（録画 ${recordedDataCount}件）` : 'データ一覧'
  );

  function openSettings(): void {
    isSettingsOpen = true;
  }

  function toggleDrawer(): void {
    bottomDrawerRef?.toggle();
  }

  function updateRecordedDataCount(count: number): void {
    recordedDataCount = count;
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
      } else if (event.type === 'domain.process.sleep.cancelled') {
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
    <button
      class="icon-button settings-button drawer-button"
      type="button"
      aria-label={drawerButtonLabel}
      onclick={(e) => {
        e.stopPropagation();
        toggleDrawer();
      }}
      title={drawerButtonLabel}
    >
      <span class="drawer-icon-wrapper">
        <PanelBottom class="icon" aria-hidden="true" stroke-width={1.75} />
        {#if recordedDataCount > 0}
          <span
            class="drawer-button-badge"
            data-testid="drawer-button-recorded-count"
            aria-hidden="true"
          >
            {recordedDataCount}
          </span>
        {/if}
      </span>
    </button>
    <div class="header-spacer"></div>
    <h1>Splat Replay</h1>
    <button
      class="icon-button settings-button"
      type="button"
      aria-label="Settings"
      onclick={openSettings}
      title="設定"
      data-testid="settings-button"
    >
      <Settings class="icon" aria-hidden="true" stroke-width={1.75} />
    </button>
  </div>

  <div class="preview-container">
    <VideoPreviewContainer />
  </div>

  <BottomDrawer bind:this={bottomDrawerRef} onRecordedCountChange={updateRecordedDataCount} />

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
    --app-horizontal-padding: 2rem;
    --app-top-padding: 1rem;
    --app-title-row-height: 2.75rem;
    --app-title-preview-gap: 1.5rem;
    --preview-drawer-gap: 1.5rem;
    --bottom-drawer-reserved-height: 5.75rem;
    --main-preview-available-height: calc(
      100vh - var(--app-top-padding) - var(--app-title-row-height) - var(--app-title-preview-gap) -
        var(--bottom-drawer-reserved-height) - var(--preview-drawer-gap)
    );
    padding: var(--app-top-padding) var(--app-horizontal-padding)
      calc(var(--bottom-drawer-reserved-height) + var(--preview-drawer-gap) + 8px);
    max-width: 1400px;
    margin: 0 auto;
    height: 100vh;
    display: flex;
    flex-direction: column;
    gap: var(--app-title-preview-gap);
    overflow: hidden;
    box-sizing: border-box;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    min-height: var(--app-title-row-height);
    margin-bottom: 0;
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
    line-height: 1.1;
    margin: 0;
    max-width: calc(100% - 7rem);
    position: absolute;
    left: 50%;
    top: 35%;
    transform: translateX(-50%) translateY(-50%);
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
    flex: 1 1 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 0;
    padding: 0;
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
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
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

  /* ドロワーフロートボタン: デフォルト非表示、高さ不足時のみ表示 */
  .drawer-button {
    display: none;
    position: relative;
  }

  .drawer-icon-wrapper {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .drawer-button-badge {
    display: flex;
    position: absolute;
    top: -0.4rem;
    right: -0.55rem;
    min-width: 1rem;
    height: 1rem;
    padding: 0 0.2rem;
    background: var(--accent-color);
    color: var(--theme-color-black);
    font-size: 0.6rem;
    font-weight: 700;
    line-height: 1rem;
    border-radius: 0.5rem;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 4px rgba(var(--theme-rgb-black), 0.4);
    pointer-events: none;
  }

  @media (max-width: 768px) {
    .app-shell {
      --app-horizontal-padding: 1rem;
    }

    h1 {
      font-size: 2.25rem;
    }
  }

  /* 高さが不足する場合: ドロワー予約領域を解放してフロートボタン表示 */
  @media (max-height: 550px) {
    .app-shell {
      --bottom-drawer-reserved-height: 0rem;
      --preview-drawer-gap: 0rem;
      --app-top-padding: 0.5rem;
      --app-title-preview-gap: 0.5rem;
      padding-bottom: 8px;
    }

    h1 {
      font-size: 2.25rem;
    }

    .header-spacer {
      display: none;
    }

    .drawer-button {
      display: inline-flex;
    }
  }
</style>
