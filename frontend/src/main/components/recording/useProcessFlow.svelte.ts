/**
 * プロセスフロー composable
 *
 * SSE 購読・ステータスポーリング・処理実行・ダイアログ管理を担当する。
 * BottomDrawer の UI ロジックとは分離し、テスト可能にする。
 */

import {
  subscribeDomainEvents,
  type DomainEvent,
  type EditUploadCompletedPayload,
} from '../../domainEvents';
import { startEditUploadProcess, fetchEditUploadStatus } from '../../api/assets';
import type { EditUploadStatus } from '../../api/types';
import { getProcessStatusPollIntervalMs, renderMode } from '../../renderMode';

export interface ProcessFlowConfig {
  onDataReload: () => void;
}

export function createProcessFlow(config: ProcessFlowConfig) {
  // --- リアクティブ状態 ---
  let processStatus = $state<EditUploadStatus | null>(null);
  const isProcessing = $derived(
    processStatus?.state === 'running' || processStatus?.state === 'cancelling'
  );
  let showProgressDialog = $state(false);
  let showAlertDialog = $state(false);
  let alertMessage = $state('');
  let alertVariant = $state<'info' | 'success' | 'warning' | 'error'>('info');
  let showYouTubePermissionDialog = $state(false);

  // --- 非リアクティブ内部状態 ---
  let statusPollingInterval: number | null = null;
  let assetEventSource: ReturnType<typeof subscribeDomainEvents> | null = null;
  let assetEventRetryTimer: number | null = null;
  let isSyncingProcessStatus = false;
  let processStatusPollIntervalMs = getProcessStatusPollIntervalMs('cpu');

  // --- renderMode 同期 ---
  $effect(() => {
    const unsubscribe = renderMode.subscribe((mode) => {
      const next = getProcessStatusPollIntervalMs(mode);
      if (processStatusPollIntervalMs !== next) {
        processStatusPollIntervalMs = next;
        if (statusPollingInterval !== null) {
          startStatusPolling();
        }
      }
    });
    return unsubscribe;
  });

  // --- 関数 ---

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
      // 接続確立時にデータを再取得（バックエンド起動遅延への対策）
      config.onDataReload();
    };
  }

  function handleAssetEvent(event: DomainEvent): void {
    if (event.type === 'domain.process.edit_upload_completed') {
      const payload = event.payload as unknown as EditUploadCompletedPayload;
      handleEditUploadCompleted(payload);
      return;
    }

    if (event.type === 'domain.process.started') {
      void syncProcessStatusFromServer();
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
    config.onDataReload();
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
    const cancelled = payload.cancelled === true;
    processStatus = {
      state: payload.success ? 'succeeded' : cancelled ? 'cancelled' : 'failed',
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
    } else if (cancelled) {
      alertMessage = payload.message || '編集・アップロード処理をキャンセルしました';
      alertVariant = 'info';
    } else {
      const detail = payload.message || '不明なエラー';
      alertMessage = `編集・アップロード処理が失敗しました: ${detail}`;
      alertVariant = 'error';
    }
    showAlertDialog = true;

    config.onDataReload();
  }

  function startStatusPolling(): void {
    // 既存のポーリングをクリア
    if (statusPollingInterval !== null) {
      clearInterval(statusPollingInterval);
    }

    // render_mode に応じた間隔で状況をチェック
    statusPollingInterval = window.setInterval(async () => {
      try {
        const status = await fetchEditUploadStatus();
        processStatus = status;

        // 処理が完了したらポーリング停止
        if (
          status.state === 'succeeded' ||
          status.state === 'failed' ||
          status.state === 'cancelled'
        ) {
          if (statusPollingInterval !== null) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
          }
          // データを再取得
          config.onDataReload();

          if (status.state === 'succeeded') {
            alertMessage = '編集・アップロード処理が完了しました!';
            alertVariant = 'success';
            showAlertDialog = true;
          } else if (status.state === 'failed') {
            alertMessage = `編集・アップロード処理が失敗しました: ${status.error || '不明なエラー'}`;
            alertVariant = 'error';
            showAlertDialog = true;
          } else {
            alertMessage = status.error || '編集・アップロード処理をキャンセルしました';
            alertVariant = 'info';
            showAlertDialog = true;
          }
        }
      } catch (error) {
        console.error('状況取得エラー:', error);
      }
    }, processStatusPollIntervalMs);
  }

  function applyRunningProcessStatus(status: EditUploadStatus): void {
    processStatus = status;
    showProgressDialog = true;
    startStatusPolling();
  }

  async function syncProcessStatusFromServer(): Promise<void> {
    if (isSyncingProcessStatus) {
      return;
    }
    isSyncingProcessStatus = true;
    try {
      const status = await fetchEditUploadStatus();
      if (status.state === 'running' || status.state === 'cancelling') {
        applyRunningProcessStatus(status);
      }
    } catch (error) {
      console.error('迥ｶ豕∝叙蠕励お繝ｩ繝ｼ:', error);
    } finally {
      isSyncingProcessStatus = false;
    }
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
        config.onDataReload();
      } else if (response.status.state === 'running') {
        applyRunningProcessStatus(response.status);
        config.onDataReload();
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

  function startAutoProcessing(): void {
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

  function handleAlertDialogClose(): void {
    showAlertDialog = false;
  }

  function destroy(): void {
    if (statusPollingInterval !== null) {
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }
    if (assetEventSource !== null) {
      assetEventSource.close();
      assetEventSource = null;
    }
    if (assetEventRetryTimer !== null) {
      window.clearTimeout(assetEventRetryTimer);
      assetEventRetryTimer = null;
    }
  }

  return {
    // リアクティブ状態 (getter/setter)
    get processStatus() {
      return processStatus;
    },
    get isProcessing() {
      return isProcessing;
    },
    get showProgressDialog() {
      return showProgressDialog;
    },
    set showProgressDialog(v: boolean) {
      showProgressDialog = v;
    },
    get showAlertDialog() {
      return showAlertDialog;
    },
    get alertMessage() {
      return alertMessage;
    },
    get alertVariant() {
      return alertVariant;
    },
    get showYouTubePermissionDialog() {
      return showYouTubePermissionDialog;
    },
    set showYouTubePermissionDialog(v: boolean) {
      showYouTubePermissionDialog = v;
    },

    // メソッド
    connectAssetEventStream,
    syncProcessStatusFromServer,
    startAutoProcessing,
    startProcessing,
    handleYouTubePermissionDialogClose,
    handleAlertDialogClose,
    openProgress: syncProcessStatusFromServer,
    destroy,
  };
}
