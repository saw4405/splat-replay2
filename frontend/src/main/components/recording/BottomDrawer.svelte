<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { slide } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import RecordedDataList from '../assets/RecordedDataList.svelte';
  import EditedDataList from '../assets/EditedDataList.svelte';
  import ProgressDialog from '../progress/ProgressDialog.svelte';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import YouTubePermissionDialog from '../permission/YouTubePermissionDialog.svelte';
  import { fetchRecordedVideos, fetchEditedVideos } from '../../api/assets';
  import { startEditUploadProcess, fetchEditUploadStatus } from '../../api/assets';
  import type { RecordedVideo, EditedVideo, EditUploadStatus } from '../../api/types';
  import {
    subscribeDomainEvents,
    type DomainEvent,
    type EditUploadCompletedPayload,
  } from '../../domainEvents';
  import { getProcessStatusPollIntervalMs, renderMode } from '../../renderMode';

  // 展開状態: "closed" | "full"
  type DrawerState = 'closed' | 'full';
  let drawerState: DrawerState = 'closed';
  let activeTab: 'recorded' | 'edited' = 'recorded';
  let recordedCount = 0;
  let editedCount = 0;
  let isProcessing = false;
  let isModalOpen = false; // モーダルが開いているかどうか
  let showProgressDialog = false; // 進捗ダイアログ表示フラグ
  let showAlertDialog = false; // アラートダイアログ表示フラグ
  let alertMessage = ''; // アラートメッセージ
  let alertVariant: 'info' | 'success' | 'warning' | 'error' = 'info';
  let showYouTubePermissionDialog = false; // YouTube権限ダイアログ表示フラグ

  let recordedVideos: RecordedVideo[] = [];
  let editedVideos: EditedVideo[] = [];
  let processStatus: EditUploadStatus | null = null;

  let statusPollingInterval: number | null = null;
  let assetEventSource: EventSource | null = null;
  let assetEventRetryTimer: number | null = null;
  let isLoadingData = false;
  let pendingDataReload = false;
  let drawerElement: HTMLDivElement | null = null;
  let modalCloseTimer: number | null = null; // モーダル閉じるタイマー
  let processStatusPollIntervalMs = getProcessStatusPollIntervalMs('cpu');

  $: recordedCount = recordedVideos.length;
  $: editedCount = editedVideos.length;
  $: isProcessing = processStatus?.state === 'running';
  $: nextProcessStatusPollIntervalMs = getProcessStatusPollIntervalMs($renderMode);
  $: if (processStatusPollIntervalMs !== nextProcessStatusPollIntervalMs) {
    processStatusPollIntervalMs = nextProcessStatusPollIntervalMs;
    if (statusPollingInterval !== null) {
      startStatusPolling();
    }
  }

  onMount(() => {
    // 初回データ取得
    void loadData();
    connectAssetEventStream();
    // グローバルクリックイベントリスナーを追加
    document.addEventListener('click', handleOutsideClick);
  });

  onDestroy(() => {
    if (statusPollingInterval !== null) {
      clearInterval(statusPollingInterval);
    }
    if (assetEventSource !== null) {
      assetEventSource.close();
      assetEventSource = null;
    }
    if (assetEventRetryTimer !== null) {
      window.clearTimeout(assetEventRetryTimer);
      assetEventRetryTimer = null;
    }
    if (modalCloseTimer !== null) {
      window.clearTimeout(modalCloseTimer);
      modalCloseTimer = null;
    }
    // グローバルクリックイベントリスナーを削除
    document.removeEventListener('click', handleOutsideClick);
  });

  async function loadData(): Promise<void> {
    if (isLoadingData) {
      pendingDataReload = true;
      return;
    }
    isLoadingData = true;
    try {
      console.log('[BottomDrawer] Loading asset data...');
      const [recorded, edited] = await Promise.all([fetchRecordedVideos(), fetchEditedVideos()]);
      recordedVideos = recorded;
      editedVideos = edited;
      console.log(
        `[BottomDrawer] Asset data loaded: ${recorded.length} recorded, ${edited.length} edited`
      );
    } catch (error) {
      console.error('データ取得エラー:', error);
    } finally {
      isLoadingData = false;
      if (pendingDataReload) {
        pendingDataReload = false;
        await loadData();
      }
    }
  }

  function connectAssetEventStream(): void {
    if (assetEventSource !== null) {
      assetEventSource.close();
      assetEventSource = null;
    }
    if (assetEventRetryTimer !== null) {
      window.clearTimeout(assetEventRetryTimer);
      assetEventRetryTimer = null;
    }

    console.log('[BottomDrawer] Connecting to /api/events/domain-events');
    assetEventSource = subscribeDomainEvents((event: DomainEvent) => {
      handleAssetEvent(event);
    });
    assetEventSource.onerror = () => {
      console.error('[BottomDrawer] SSE connection error (domain-events)');
      if (assetEventSource !== null) {
        assetEventSource.close();
        assetEventSource = null;
      }
      if (assetEventRetryTimer === null) {
        assetEventRetryTimer = window.setTimeout(() => {
          assetEventRetryTimer = null;
          connectAssetEventStream();
        }, 5000);
      }
    };
    assetEventSource.onopen = () => {
      console.log('[BottomDrawer] SSE connection opened (domain-events)');
    };
  }

  function handleAssetEvent(event: DomainEvent): void {
    if (event.type === 'domain.process.edit_upload_completed') {
      const payload = event.payload as unknown as EditUploadCompletedPayload;
      handleEditUploadCompleted(payload);
      return;
    }

    const assetEventTypes = new Set([
      'domain.asset.recorded.saved',
      'domain.asset.recorded.metadata_updated',
      'domain.asset.recorded.subtitle_updated',
      'domain.asset.recorded.deleted',
      'domain.asset.edited.saved',
      'domain.asset.edited.deleted',
    ]);
    if (!assetEventTypes.has(event.type)) {
      return;
    }
    console.log('[BottomDrawer] Asset event received:', event.type);
    void loadData();
  }

  function handleEditUploadCompleted(payload: EditUploadCompletedPayload): void {
    if (statusPollingInterval !== null) {
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }

    const finishedAt = new Date().toISOString();
    const startedAt = processStatus?.startedAt ?? null;
    const sleepAfterUploadDefault = processStatus?.sleepAfterUploadDefault ?? false;
    const sleepAfterUploadEffective =
      payload.sleep_after_upload ?? processStatus?.sleepAfterUploadEffective ?? false;
    processStatus = {
      state: payload.success ? 'succeeded' : 'failed',
      startedAt,
      finishedAt,
      error: payload.success ? null : payload.message,
      sleepAfterUploadDefault,
      sleepAfterUploadEffective,
      sleepAfterUploadOverridden: sleepAfterUploadEffective !== sleepAfterUploadDefault,
    };

    showProgressDialog = false;

    if (payload.success) {
      alertMessage = payload.message || '編集・アップロード処理が完了しました!';
      alertVariant = 'success';
    } else {
      const detail = payload.message || '不明なエラー';
      alertMessage = `編集・アップロード処理が失敗しました: ${detail}`;
      alertVariant = 'error';
    }
    showAlertDialog = true;

    void loadData();
  }

  function handleOutsideClick(event: MouseEvent): void {
    if (drawerState === 'closed' || !drawerElement || isModalOpen) {
      return;
    }

    const target = event.target as Node;
    // ドロワー要素の外側をクリックした場合のみ閉じる
    if (!drawerElement.contains(target)) {
      drawerState = 'closed';
    }
  }

  function toggleDrawer(): void {
    if (drawerState === 'closed') {
      drawerState = 'full';
    } else {
      drawerState = 'closed';
    }
  }

  function activateTab(tab: 'recorded' | 'edited', event?: MouseEvent | KeyboardEvent): void {
    if (event) {
      event.stopPropagation();
    }
    activeTab = tab;
    drawerState = 'full';
  }

  async function startProcessing(): Promise<void> {
    if (isProcessing) return;

    try {
      // YouTube権限ダイアログを表示済みか確認
      const dialogResponse = await fetch('/api/settings/youtube-permission-dialog');
      const dialogStatus = (await dialogResponse.json()) as { shown: boolean };

      if (!dialogStatus.shown) {
        // ダイアログを表示
        showYouTubePermissionDialog = true;
        return;
      }

      // 処理を開始
      await executeProcessing();
    } catch (error) {
      console.error('処理開始エラー:', error);
      alertMessage = `処理開始に失敗しました: ${error}`;
      alertVariant = 'error';
      showAlertDialog = true;
    }
  }

  async function executeProcessing(auto: boolean = false): Promise<void> {
    try {
      // 進捗ダイアログを表示
      showProgressDialog = true;
      const response = await startEditUploadProcess({ auto });
      if (response.accepted) {
        processStatus = response.status;
        // 処理状態のポーリング開始
        startStatusPolling();
        await loadData(); // データを即座に再取得
      } else {
        alertMessage = response.message || '処理を開始できませんでした(既に実行中の可能性)';
        alertVariant = 'warning';
        showAlertDialog = true;
      }
    } catch (error) {
      console.error('処理開始エラー:', error);
      alertMessage = `処理開始に失敗しました: ${error}`;
      alertVariant = 'error';
      showAlertDialog = true;
    }
  }

  /**
   * 自動処理通知から実行を開始する。
   */
  export function startAutoProcessing(): void {
    if (isProcessing) {
      showProgressDialog = true;
      startStatusPolling();
      return;
    }
    void executeProcessing(true);
  }

  function handleYouTubePermissionDialogClose(): void {
    showYouTubePermissionDialog = false;
    // ダイアログを閉じた後、処理を開始
    void executeProcessing();
  }

  function startStatusPolling(): void {
    // 既存のポーリングをクリア
    if (statusPollingInterval !== null) {
      clearInterval(statusPollingInterval);
    }

    // render_mode に応じた間隔で状態をチェック
    statusPollingInterval = window.setInterval(async () => {
      try {
        const status = await fetchEditUploadStatus();
        processStatus = status;

        // 処理が完了したらポーリング停止
        if (status.state === 'succeeded' || status.state === 'failed') {
          if (statusPollingInterval !== null) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
          }
          // データを再取得
          await loadData();

          if (status.state === 'succeeded') {
            alertMessage = '編集・アップロード処理が完了しました!';
            alertVariant = 'success';
            showAlertDialog = true;
          } else if (status.state === 'failed') {
            alertMessage = `編集・アップロード処理が失敗しました: ${status.error || '不明なエラー'}`;
            alertVariant = 'error';
            showAlertDialog = true;
          }
        }
      } catch (error) {
        console.error('状態取得エラー:', error);
      }
    }, processStatusPollIntervalMs);
  }

  /**
   * 外部（MainAppなど）から進捗表示を開始するための関数
   */
  export function openProgress(): void {
    showProgressDialog = true;
    startStatusPolling();
  }
</script>

<!-- YouTube権限ダイアログ -->
<YouTubePermissionDialog
  bind:open={showYouTubePermissionDialog}
  on:close={handleYouTubePermissionDialogClose}
/>

<!-- 進捗ダイアログ -->
<ProgressDialog isOpen={showProgressDialog} on:close={() => (showProgressDialog = false)} />

<!-- アラートダイアログ -->
<NotificationDialog
  isOpen={showAlertDialog}
  variant={alertVariant}
  message={alertMessage}
  on:close={() => (showAlertDialog = false)}
/>

<div class="bottom-drawer" class:full={drawerState === 'full'} bind:this={drawerElement}>
  <!-- ヘッダーバー (常時表示) -->
  <div
    class="drawer-header"
    role="button"
    tabindex="0"
    on:click={toggleDrawer}
    on:keydown={(e) => e.key === 'Enter' && toggleDrawer()}
    data-testid="bottom-drawer-toggle"
  >
    <div class="header-left">
      <div class="expand-hint">
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M5 7.5L10 12.5L15 7.5"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="expand-arrow"
            class:full={drawerState === 'full'}
          />
        </svg>
        <span class="hint-text">
          {#if drawerState === 'closed'}
            詳細を表示
          {:else}
            閉じる
          {/if}
        </span>
      </div>
      <div class="tabs">
        <button
          class="tab recorded"
          class:has-data={recordedCount > 0}
          class:active={drawerState === 'full' && activeTab === 'recorded'}
          on:click={(e) => activateTab('recorded', e)}
          on:keydown={(e) => e.key === 'Enter' && activateTab('recorded', e)}
        >
          <div class="tab-glow"></div>
          <span class="tab-icon">🎬</span>
          <div class="tab-info">
            <span class="tab-label">録画済</span>
            <span class="tab-count" data-testid="recorded-count">{recordedCount}</span>
          </div>
        </button>

        <button
          class="tab edited"
          class:has-data={editedCount > 0}
          class:active={drawerState === 'full' && activeTab === 'edited'}
          on:click={(e) => activateTab('edited', e)}
          on:keydown={(e) => e.key === 'Enter' && activateTab('edited', e)}
        >
          <div class="tab-glow"></div>
          <span class="tab-icon">✨</span>
          <div class="tab-info">
            <span class="tab-label">編集済</span>
            <span class="tab-count">{editedCount}</span>
          </div>
        </button>
      </div>
    </div>

    <div class="header-right">
      <button
        class="process-button"
        class:processing={isProcessing}
        class:ready={recordedCount > 0 || editedCount > 0}
        disabled={isProcessing || (recordedCount === 0 && editedCount === 0)}
        on:click|stopPropagation={async () => {
          await startProcessing();
        }}
        title="録画データの編集とYouTubeへのアップロードを開始します"
      >
        <div class="button-background"></div>
        <div class="button-content">
          {#if isProcessing}
            <span class="spinner"></span>
            <span>処理中...</span>
          {:else}
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              class="play-icon"
            >
              <path d="M3 2L13 8L3 14V2Z" fill="currentColor" />
            </svg>
            <span>処理開始</span>
          {/if}
        </div>
      </button>
    </div>
  </div>

  <!-- 展開コンテンツ -->
  {#if drawerState !== 'closed'}
    <div class="drawer-content" transition:slide={{ duration: 250, easing: cubicOut }}>
      <div class="tab-content">
        {#if activeTab === 'recorded'}
          <!-- 録画済データ -->
          <div class="data-section">
            <h3 class="section-title">
              <span class="title-icon">🎬</span>
              録画済データ ({recordedCount}件)
            </h3>
            <div class="list-container">
              <RecordedDataList
                videos={recordedVideos}
                on:refresh={loadData}
                on:modalOpen={() => {
                  console.log('BottomDrawer: modalOpen event received from RecordedDataList');
                  drawerState = 'full';
                  isModalOpen = true;
                  console.log(
                    'BottomDrawer: drawerState =',
                    drawerState,
                    ', isModalOpen =',
                    isModalOpen
                  );
                }}
                on:modalClose={() => {
                  console.log('BottomDrawer: modalClose event received from RecordedDataList');
                  // モーダルが閉じた直後のクリックイベントを無視するため、少し遅延
                  if (modalCloseTimer !== null) {
                    window.clearTimeout(modalCloseTimer);
                  }
                  modalCloseTimer = window.setTimeout(() => {
                    isModalOpen = false;
                    modalCloseTimer = null;
                    console.log(
                      'BottomDrawer: drawerState =',
                      drawerState,
                      ', isModalOpen =',
                      isModalOpen
                    );
                  }, 100);
                }}
              />
            </div>
          </div>
        {:else if activeTab === 'edited'}
          <!-- 編集済データ -->
          <div class="data-section">
            <h3 class="section-title">
              <span class="title-icon">✨</span>
              編集済データ ({editedCount}件)
            </h3>
            <div class="list-container">
              <EditedDataList
                videos={editedVideos}
                on:refresh={loadData}
                on:modalOpen={() => {
                  console.log('BottomDrawer: modalOpen event received from EditedDataList');
                  drawerState = 'full';
                  isModalOpen = true;
                  console.log(
                    'BottomDrawer: drawerState =',
                    drawerState,
                    ', isModalOpen =',
                    isModalOpen
                  );
                }}
                on:modalClose={() => {
                  console.log('BottomDrawer: modalClose event received from EditedDataList');
                  // モーダルが閉じた直後のクリックイベントを無視するため、少し遅延
                  if (modalCloseTimer !== null) {
                    window.clearTimeout(modalCloseTimer);
                  }
                  modalCloseTimer = window.setTimeout(() => {
                    isModalOpen = false;
                    modalCloseTimer = null;
                    console.log(
                      'BottomDrawer: drawerState =',
                      drawerState,
                      ', isModalOpen =',
                      isModalOpen
                    );
                  }, 100);
                }}
              />
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .bottom-drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: auto;
    max-height: 100vh;
    display: flex;
    flex-direction: column;
    background: linear-gradient(
      to top,
      rgba(var(--theme-rgb-surface-deep), 0.98) 0%,
      rgba(var(--theme-rgb-surface-overlay), 0.95) 50%,
      rgba(var(--theme-rgb-space-2), 0.92) 100%
    );
    backdrop-filter: blur(12px) saturate(145%);
    -webkit-backdrop-filter: blur(12px) saturate(145%);
    border-top: 1px solid rgba(var(--theme-rgb-accent), 0.2);
    box-shadow:
      0 -6px 22px rgba(var(--theme-rgb-black), 0.3),
      0 -2px 6px rgba(var(--theme-rgb-accent), 0.08),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.05);
    z-index: 100;
    transition: box-shadow 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .bottom-drawer.full {
    box-shadow:
      0 -8px 28px rgba(var(--theme-rgb-black), 0.34),
      0 -3px 10px rgba(var(--theme-rgb-accent), 0.12),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.05);
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 1rem 1.5rem;
    cursor: pointer;
    transition: background 0.3s ease;
    border-bottom: 1px solid rgba(var(--theme-rgb-white), 0.05);
    position: relative;
    overflow: hidden;
    flex: 0 0 auto;
  }

  .drawer-header::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      rgba(var(--theme-rgb-accent), 0) 0%,
      rgba(var(--theme-rgb-accent), 0.03) 50%,
      rgba(var(--theme-rgb-accent), 0) 100%
    );
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
  }

  .drawer-header:hover::before {
    opacity: 1;
  }

  .drawer-header:hover {
    background: rgba(var(--theme-rgb-accent), 0.02);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 2rem;
    flex: 1;
  }

  .expand-hint {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 0.85rem;
    transition: all 0.3s ease;
  }

  .drawer-header:hover .expand-hint {
    color: var(--accent-color);
  }

  .expand-arrow {
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .expand-arrow.full {
    transform: rotate(180deg) scale(1.2);
  }

  .hint-text {
    font-weight: 500;
    letter-spacing: 0.02em;
  }

  .tabs {
    display: flex;
    gap: 1rem;
  }

  .tab {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.65rem 1.25rem;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.06) 0%,
      rgba(var(--theme-rgb-white), 0.03) 100%
    );
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
    border-radius: 12px;
    font-size: 0.95rem;
    color: inherit;
    cursor: pointer;
    transition:
      border-color 0.2s ease,
      background 0.2s ease,
      box-shadow 0.2s ease;
    overflow: hidden;
  }

  .tab-glow {
    position: absolute;
    inset: -1px;
    border-radius: 12px;
    opacity: 0;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.3) 0%,
      rgba(var(--theme-rgb-accent), 0.1) 100%
    );
    filter: blur(5px);
    transition: opacity 0.3s ease;
    z-index: -1;
  }

  .tab.has-data .tab-glow {
    opacity: 1;
  }

  .tab:hover {
    border-color: rgba(var(--theme-rgb-accent), 0.3);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.08) 0%,
      rgba(var(--theme-rgb-white), 0.05) 100%
    );
  }

  .tab.has-data {
    border-color: rgba(var(--theme-rgb-accent), 0.2);
  }

  .tab.active {
    border-color: var(--accent-color);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.15) 0%,
      rgba(var(--theme-rgb-accent), 0.05) 100%
    );
    box-shadow: 0 0 12px rgba(var(--theme-rgb-accent), 0.2);
  }

  .tab.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 20%;
    right: 20%;
    height: 3px;
    background: var(--accent-color);
    border-radius: 3px 3px 0 0;
    box-shadow: 0 -2px 8px rgba(var(--theme-rgb-accent), 0.6);
  }

  .tab-icon {
    font-size: 1.3rem;
    filter: drop-shadow(0 2px 4px rgba(var(--theme-rgb-black), 0.3));
  }

  .tab-info {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.1rem;
    text-align: center;
  }

  .tab-label {
    color: rgba(var(--theme-rgb-white), 0.7);
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .tab-count {
    color: var(--accent-color);
    font-weight: 700;
    font-size: 1.25rem;
    line-height: 1;
    text-shadow: 0 0 6px rgba(var(--theme-rgb-accent), 0.3);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .process-button {
    position: relative;
    background: transparent;
    color: rgba(var(--theme-rgb-white), 0.5);
    border: 1px solid rgba(var(--theme-rgb-white), 0.15);
    padding: 0.85rem 2rem;
    border-radius: 12px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition:
      border-color 0.2s ease,
      box-shadow 0.2s ease,
      color 0.2s ease;
    overflow: hidden;
  }

  .button-background {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  .button-content {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    z-index: 1;
    transition: all 0.3s ease;
  }

  .process-button.ready {
    border-color: rgba(var(--theme-rgb-accent), 0.3);
    color: var(--accent-color);
  }

  .process-button.ready .button-background {
    opacity: 0.1;
  }

  .process-button.ready:hover {
    border-color: rgba(var(--theme-rgb-accent), 0.5);
    box-shadow:
      0 4px 14px rgba(var(--theme-rgb-accent), 0.18),
      0 0 16px rgba(var(--theme-rgb-accent), 0.1),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.1);
  }

  .process-button.ready:hover .button-background {
    opacity: 1;
  }

  .process-button.ready:hover .button-content {
    color: var(--theme-color-black);
  }

  .process-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none !important;
  }

  .process-button.processing {
    border-color: rgba(var(--theme-rgb-accent), 0.5);
    color: var(--accent-color);
  }

  .process-button.processing .button-background {
    opacity: 0.2;
  }

  .spinner {
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border: 2px solid rgba(var(--theme-rgb-black), 0.3);
    border-top-color: var(--theme-color-black);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .drawer-content {
    height: calc(100vh - 84px);
    overflow-y: auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
  }

  .drawer-content::after {
    content: '';
    flex: 0 0 0.5rem;
  }

  .tab-content {
    display: flex;
    flex-direction: column;
    width: 100%;
    flex: 1;
    min-height: 0;
  }

  .data-section {
    background: rgba(var(--theme-rgb-white), 0.03);
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.08);
    overflow-wrap: break-word; /* 長い単語を折り返す */
    word-wrap: break-word; /* 古いブラウザ対応 */
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden; /* コンテンツがはみ出さないようにする */
    align-self: stretch; /* ensure grid item fills the grid cell vertically/horizontally */
    width: 100%;
    gap: 1.5rem;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--accent-color);
    flex-shrink: 0;
  }

  .list-container {
    flex: 1 1 auto;
    width: 100%;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: 100%;
    align-items: stretch;
  }

  .list-container :global(.glass-scroller) {
    flex: 1 1 auto;
    min-height: 0;
  }

  .title-icon {
    font-size: 1.3rem;
  }

  /* スクロールバースタイル */
  .drawer-content::-webkit-scrollbar {
    width: 8px;
  }

  .drawer-content::-webkit-scrollbar-track {
    background: rgba(var(--theme-rgb-black), 0.2);
  }

  .drawer-content::-webkit-scrollbar-thumb {
    background: rgba(var(--theme-rgb-accent), 0.3);
    border-radius: 4px;
  }

  .drawer-content::-webkit-scrollbar-thumb:hover {
    background: rgba(var(--theme-rgb-accent), 0.5);
  }

  /* レスポンシブ対応 */
  @media (max-width: 1024px) {
    .tab-content {
      gap: 1.5rem;
    }

    .data-section {
      height: 100%;
    }

    .list-container {
      min-height: 0;
    }
  }

  @media (max-width: 768px) {
    .drawer-header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      column-gap: 1rem;
      row-gap: 0.75rem;
    }

    .header-left {
      gap: 1rem;
      flex-wrap: wrap;
      align-items: center;
      min-width: 0;
    }

    .tabs {
      flex-wrap: wrap;
      column-gap: 0.75rem;
      row-gap: 0.5rem;
    }

    .process-button {
      justify-self: end;
      width: auto;
    }
  }
</style>
