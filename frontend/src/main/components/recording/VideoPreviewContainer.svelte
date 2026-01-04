<script lang="ts">
  import { onMount } from 'svelte';
  import { Info, X } from 'lucide-svelte';
  import VideoPreview from './VideoPreview.svelte';
  import VideoPreviewMessage from './VideoPreviewMessage.svelte';
  import MetadataOverlay from '../metadata/MetadataOverlay.svelte';
  import CameraPermissionDialog from '../permission/CameraPermissionDialog.svelte';
  import { subscribeDomainEvents, type DomainEvent } from '../../domainEvents';

  type PreviewState = 'checking' | 'connected' | 'disconnected' | 'error';

  type StartRecordingResponse = {
    success: boolean;
    error?: string;
  };

  type PrepareRecordingResponse = {
    success: boolean;
    error?: string;
  };

  const DEVICE_POLL_INTERVAL_MS = 1000;
  const NOTIFICATION_DURATION_MS = 5000;

  let isRecording = false;
  let startPending = false;
  let preparePending = false;
  let _status = 'デバイス確認中...';
  let deviceState: PreviewState = 'checking';
  let deviceErrorMessage = '';
  let deviceStatusTimer: number | null = null;
  let isPrepared = false;
  let isMetadataOpen = false;
  let isRefreshingDeviceStatus = false; // 多重実行防止フラグ
  let isCameraPermissionDialogOpen = false;
  type MetadataValue = string | number | null | undefined;
  type MetadataFieldKey =
    | 'game_mode'
    | 'rule'
    | 'stage'
    | 'match'
    | 'started_at'
    | 'rate'
    | 'judgement'
    | 'kill'
    | 'death'
    | 'special';
  type MetadataEventPayload = Partial<Record<MetadataFieldKey, MetadataValue>>;
  type MetadataNotification = {
    id: number;
    text: string;
    timer: ReturnType<typeof window.setTimeout>;
  };
  type MetadataFieldDescriptor = {
    key: MetadataFieldKey;
    label: string;
    format: (value: MetadataValue) => string | null;
    normalize?: (value: MetadataValue) => string | null;
  };
  const PLACEHOLDER_VALUES = new Set(['未取得', '']);
  const startedAtFormatter = new Intl.DateTimeFormat('ja-JP', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
  const metadataFieldDescriptors: MetadataFieldDescriptor[] = [
    { key: 'game_mode', label: 'モード', format: formatTextValue },
    { key: 'match', label: 'マッチタイプ', format: formatTextValue },
    { key: 'rule', label: 'ルール', format: formatTextValue },
    { key: 'stage', label: 'ステージ', format: formatTextValue },
    {
      key: 'started_at',
      label: 'マッチング開始時間',
      format: formatStartedAtValue,
      normalize: normalizeStartedAtValue,
    },
    { key: 'rate', label: 'レート', format: formatTextValue },
    { key: 'judgement', label: '判定', format: formatTextValue },
    { key: 'kill', label: 'キル数', format: formatNumericValue },
    { key: 'death', label: 'デス数', format: formatNumericValue },
    { key: 'special', label: 'スペシャル', format: formatNumericValue },
  ];
  let metadataNotifications: MetadataNotification[] = [];
  let notificationIdCounter = 0;
  let lastMetadata: Partial<Record<MetadataFieldKey, string>> = {};

  function toggleMetadata(): void {
    isMetadataOpen = !isMetadataOpen;
    if (isMetadataOpen) {
      // 開いたら通知を消す
      clearMetadataNotifications();
    }
  }

  function showMetadataNotification(text: string): void {
    if (isMetadataOpen) {
      // メタデータパネルが開いている時は通知しない
      return;
    }

    const id = ++notificationIdCounter;
    const timer = window.setTimeout(() => {
      removeMetadataNotification(id);
    }, NOTIFICATION_DURATION_MS);
    metadataNotifications = [
      ...metadataNotifications,
      {
        id,
        text,
        timer,
      },
    ];
  }

  function removeMetadataNotification(id: number): void {
    const target = metadataNotifications.find((notification) => notification.id === id);
    if (target) {
      window.clearTimeout(target.timer);
    }
    metadataNotifications = metadataNotifications.filter((notification) => notification.id !== id);
  }

  function clearMetadataNotifications(): void {
    metadataNotifications.forEach((notification) => {
      window.clearTimeout(notification.timer);
    });
    metadataNotifications = [];
  }

  function normalizeRawValue(value: MetadataValue): string | null {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value === 'number') {
      return value.toString();
    }
    const trimmed = value.trim();
    if (!trimmed || PLACEHOLDER_VALUES.has(trimmed)) {
      return null;
    }
    return trimmed;
  }

  function formatTextValue(value: MetadataValue): string | null {
    const normalized = normalizeRawValue(value);
    if (normalized === null) {
      return null;
    }
    return normalized;
  }

  function formatNumericValue(value: MetadataValue): string | null {
    return normalizeRawValue(value);
  }

  function formatStartedAtValue(value: MetadataValue): string | null {
    if (typeof value !== 'string') {
      return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const date = new Date(trimmed);
    if (Number.isNaN(date.getTime())) {
      return trimmed;
    }
    return startedAtFormatter.format(date);
  }

  function normalizeStartedAtValue(value: MetadataValue): string | null {
    if (typeof value !== 'string') {
      return null;
    }
    const trimmed = value.trim();
    if (!trimmed || PLACEHOLDER_VALUES.has(trimmed)) {
      return null;
    }
    // ISO形式などの日時文字列をそのまま比較用に返す
    return trimmed;
  }

  function handleMetadataUpdate(payload: MetadataEventPayload): void {
    console.log('[handleMetadataUpdate] payload:', payload);
    const updates: string[] = [];
    const nextMetadata: Partial<Record<MetadataFieldKey, string>> = {
      ...lastMetadata,
    };

    metadataFieldDescriptors.forEach(({ key, label, format, normalize }) => {
      const rawValue = payload[key];

      // payloadにキーが含まれていない場合はスキップ
      if (!(key in payload)) {
        return;
      }

      const normalizedForComparison = normalize?.(rawValue) ?? normalizeRawValue(rawValue);
      const previousValue = lastMetadata[key];

      console.log(`[handleMetadataUpdate] ${key}:`, {
        rawValue,
        normalizedForComparison,
        previousValue,
      });

      if (normalizedForComparison === null) {
        delete nextMetadata[key];
        return;
      }

      nextMetadata[key] = normalizedForComparison;
      if (previousValue === normalizedForComparison) {
        console.log(`[handleMetadataUpdate] ${key}: 値が変わっていないためスキップ`);
        return;
      }

      const formatted = format(rawValue);
      if (formatted === null) {
        console.log(`[handleMetadataUpdate] ${key}: フォーマット結果がnullのためスキップ`);
        return;
      }

      console.log(`[handleMetadataUpdate] ${key}: 通知追加 - ${label}: ${formatted}`);
      updates.push(`${label}: ${formatted}`);
    });

    lastMetadata = nextMetadata;

    console.log(`[handleMetadataUpdate] 通知数: ${updates.length}`, updates);
    updates.forEach((text) => {
      showMetadataNotification(text);
    });
  }

  async function prepareRecording(): Promise<void> {
    if (preparePending || isPrepared) {
      return;
    }
    preparePending = true;
    try {
      status = '録画準備中 (OBS起動＆仮想カメラ有効化)...';
      const response = await fetch('/api/recorder/prepare', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const result = (await response.json()) as PrepareRecordingResponse;
      console.log('prepare_recording result:', result);
      if (result.success === true) {
        isPrepared = true;
        status = '録画準備完了';
        console.log('録画準備完了 - isPrepared =', isPrepared);
      } else {
        status = `録画準備エラー: ${result.error ?? '原因不明のエラー'}`;
        console.error('録画準備失敗:', result);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      status = `録画準備エラー: ${message}`;
      console.error('録画準備エラー:', error);
    } finally {
      preparePending = false;
    }
  }

  async function enableAutoRecording(): Promise<void> {
    if (isRecording || startPending) {
      console.log('enableAutoRecording: すでに録画中またはペンディング中', {
        isRecording,
        startPending,
      });
      return;
    }
    console.log('enableAutoRecording: 開始');
    startPending = true;
    try {
      status = '自動録画機能 ON 準備中...';
      const response = await fetch('/api/recorder/enable-auto', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const result = (await response.json()) as StartRecordingResponse;
      console.log('enable_auto_recording result:', result);
      if (result.success) {
        status = '自動録画機能 ON（バトル開始を検知中...）';
        console.log('自動録画機能 ON 成功');
      } else {
        status = `エラー: ${result.error ?? '原因不明のエラー'}`;
        console.error('自動録画有効化失敗:', result.error);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      status = `エラー: ${message}`;
      console.error('自動録画有効化エラー:', error);
    } finally {
      startPending = false;
    }
  }

  async function _startRecording(): Promise<void> {
    if (isRecording || startPending) {
      console.log('startRecording: すでに録画中またはペンディング中', {
        isRecording,
        startPending,
      });
      return;
    }
    console.log('startRecording: 開始');
    startPending = true;
    try {
      status = '自動録画機能 ON 準備中...';
      const response = await fetch('/api/recorder/start', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const result = (await response.json()) as StartRecordingResponse;
      console.log('start_recording result:', result);
      if (result.success) {
        isRecording = true;
        status = '自動録画機能 ON';
        console.log('自動録画機能 ON 成功');
      } else {
        status = `エラー: ${result.error ?? '原因不明のエラー'}`;
        console.error('自動録画開始失敗:', result.error);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      status = `エラー: ${message}`;
      console.error('自動録画開始エラー:', error);
    } finally {
      startPending = false;
    }
  }

  async function refreshDeviceStatus(): Promise<void> {
    // 多重実行防止: すでに実行中の場合はスキップ
    if (isRefreshingDeviceStatus) {
      console.log('[refreshDeviceStatus] すでに実行中のためスキップ');
      return;
    }

    isRefreshingDeviceStatus = true;
    try {
      const response = await fetch('/api/device/status', {
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const connected = (await response.json()) as boolean;
      updateDeviceState(connected ? 'connected' : 'disconnected');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'device status unknown';
      updateDeviceState('error', message);
    } finally {
      isRefreshingDeviceStatus = false;
    }
  }

  async function checkAndShowCameraPermissionDialog(): Promise<void> {
    try {
      const response = await fetch('/api/settings/camera-permission-dialog');
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const data = (await response.json()) as { shown: boolean };
      if (!data.shown) {
        isCameraPermissionDialogOpen = true;
      }
    } catch (error) {
      console.error('Failed to check camera permission dialog status:', error);
    }
  }

  function updateDeviceState(nextState: PreviewState, message = ''): void {
    const previous = deviceState;
    deviceState = nextState;

    if (nextState === 'error') {
      deviceErrorMessage = message;
      const details = message ? ` (${message})` : '';
      status = `エラー: キャプチャーデバイスの状態を取得できません${details}`;
      return;
    }

    deviceErrorMessage = '';

    if (nextState === 'connected' && previous !== 'connected') {
      console.log('デバイス接続を検出 - 録画準備を開始');
      if (deviceStatusTimer !== null) {
        window.clearInterval(deviceStatusTimer);
        deviceStatusTimer = null;
      }
      // デバイス接続時にカメラ許可ダイアログをチェック
      void checkAndShowCameraPermissionDialog();
      // デバイス接続後、録画準備を実行
      void prepareRecording().then(() => {
        console.log('prepareRecording完了 - isPrepared:', isPrepared);
        if (isPrepared) {
          // 録画準備完了 - 自動録画モードを有効化
          console.log('enableAutoRecording を呼び出します');
          void enableAutoRecording();
        } else {
          console.warn('isPreparedがfalseのため自動録画を有効化できません');
        }
      });
      return;
    }

    if (nextState === 'disconnected') {
      isRecording = false;
      isPrepared = false;
      status = 'キャプチャーデバイスを接続してください';
      return;
    }

    if (nextState === 'checking' && !isRecording && !startPending && !preparePending) {
      status = 'デバイス確認中...';
    }
  }

  onMount(() => {
    void refreshDeviceStatus();
    deviceStatusTimer = window.setInterval(() => {
      void refreshDeviceStatus();
    }, DEVICE_POLL_INTERVAL_MS);

    // ドメインイベントを購読
    const domainEventSource = subscribeDomainEvents((event: DomainEvent) => {
      if (event.type === 'domain.recording.metadata_updated') {
        const payload = event.payload as { metadata?: MetadataEventPayload };
        if (payload?.metadata) {
          handleMetadataUpdate(payload.metadata);
        }
        return;
      }
      console.log('[DomainEvent]', event);
    });

    return () => {
      if (deviceStatusTimer !== null) {
        window.clearInterval(deviceStatusTimer);
        deviceStatusTimer = null;
      }
      clearMetadataNotifications();
      domainEventSource.close();
    };
  });
</script>

<div class="preview-container glass-surface">
  {#if deviceState === 'connected'}
    <div class="metadata-button-container">
      <button
        class="metadata-toggle-btn glass-icon-button"
        type="button"
        on:click={toggleMetadata}
        aria-label={isMetadataOpen ? 'メタデータを閉じる' : 'メタデータを表示'}
        title={isMetadataOpen ? 'メタデータを閉じる' : 'メタデータを表示'}
      >
        {#if isMetadataOpen}
          <X class="icon" aria-hidden="true" stroke-width={1.75} />
        {:else}
          <Info class="icon" aria-hidden="true" stroke-width={1.75} />
        {/if}
      </button>
      {#if !isMetadataOpen && metadataNotifications.length > 0}
        <div class="metadata-notifications">
          {#each metadataNotifications as notification (notification.id)}
            <div class="metadata-notification glass-pill">
              {notification.text}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  {#if deviceState === 'connected'}
    <VideoPreview />
  {:else if deviceState === 'checking'}
    <VideoPreviewMessage message="キャプチャーデバイスの接続状態を確認しています..." />
  {:else if deviceState === 'disconnected'}
    <VideoPreviewMessage message="キャプチャーデバイスが接続されていません" />
  {:else}
    <VideoPreviewMessage
      message={`キャプチャーデバイスの状態を取得できません${deviceErrorMessage ? ` (${deviceErrorMessage})` : ''}`}
    />
  {/if}

  {#if deviceState === 'connected'}
    <MetadataOverlay bind:visible={isMetadataOpen} />
  {/if}
</div>

<CameraPermissionDialog bind:open={isCameraPermissionDialogOpen} />

<style>
  .preview-container {
    position: relative;
    width: 100%;
    max-width: min(1280px, calc((100vh - 180px) * 16 / 9));
    max-height: calc(100vh - 180px);
    aspect-ratio: 16 / 9;
    margin: 2rem;
    display: flex;
    align-items: stretch;
    overflow: hidden;
    --preview-radius: calc(var(--glass-radius) + 8px);
    border-radius: var(--preview-radius);
    box-shadow:
      var(--glass-shadow),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .preview-container :global(.video-preview) {
    width: 100%;
    height: 100%;
    flex: 1 1 auto;
    border-radius: inherit;
    --preview-radius: inherit;
  }

  .metadata-button-container {
    position: absolute;
    top: 1rem;
    right: 1rem;
    z-index: 200;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
  }

  .metadata-toggle-btn {
    width: 2.75rem;
    height: 2.75rem;
    min-width: 2.75rem;
    min-height: 2.75rem;
    font-size: 1.25rem;
    color: var(--text-primary);
    border-radius: 50%;
    border: 1px solid var(--glass-border);
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    box-shadow:
      0 10px 24px rgba(0, 0, 0, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.12);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    box-sizing: border-box;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .metadata-toggle-btn:hover {
    transform: translateY(-2px) scale(1.05);
    border-color: rgba(25, 211, 199, 0.45);
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.04) 100%
    );
    box-shadow:
      0 16px 32px rgba(0, 0, 0, 0.35),
      0 0 22px rgba(25, 211, 199, 0.25);
  }

  .metadata-toggle-btn:focus-visible {
    outline: none;
    border-color: rgba(25, 211, 199, 0.55);
    box-shadow:
      0 0 0 3px rgba(3, 12, 20, 0.9),
      0 0 0 6px rgba(25, 211, 199, 0.35),
      0 18px 38px rgba(25, 211, 199, 0.35);
  }

  .metadata-toggle-btn:active {
    transform: scale(0.95);
    box-shadow:
      0 8px 18px rgba(0, 0, 0, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.18);
  }

  .metadata-notifications {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    width: 100%;
  }

  .metadata-notification {
    background: linear-gradient(135deg, rgba(25, 211, 199, 1) 0%, rgba(18, 180, 170, 0.98) 100%);
    backdrop-filter: blur(10px) saturate(160%);
    -webkit-backdrop-filter: blur(10px) saturate(160%);
    border: 1px solid rgba(25, 211, 199, 0.8);
    border-radius: 999px;
    padding: 0.55rem 1rem;
    color: #021015;
    font-size: 0.85rem;
    font-weight: 700;
    white-space: nowrap;
    max-width: 250px;
    overflow: hidden;
    text-overflow: ellipsis;
    box-shadow:
      0 12px 26px rgba(25, 211, 199, 0.5),
      0 0 25px rgba(25, 211, 199, 0.4),
      inset 0 1px 0 rgba(255, 255, 255, 0.3);
    animation: slideIn 0.3s ease-out;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateX(10px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
</style>
