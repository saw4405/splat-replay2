<script lang="ts">
  import { onMount } from 'svelte';
  import { Info, X } from 'lucide-svelte';
  import VideoPreview from './VideoPreview.svelte';
  import VideoPreviewMessage from './VideoPreviewMessage.svelte';
  import MetadataOverlay from '../metadata/MetadataOverlay.svelte';
  import CameraPermissionDialog from '../permission/CameraPermissionDialog.svelte';
  import { subscribeDomainEvents, type DomainEvent } from '../../domainEvents';
  import { buildMetadataOptionMap, getMetadataOptions } from '../../api/metadata';
  import { getRecorderPreviewMode, recoverCaptureDevice } from '../../api/recording';
  import { notifyRecordingReady } from '../../notification';
  import { getDeviceStatusPollIntervalMs, renderMode } from '../../renderMode';

  type PreviewState = 'checking' | 'connected' | 'disconnected' | 'error';

  type StartRecordingResponse = {
    success: boolean;
    error?: string;
  };

  type PrepareRecordingResponse = {
    success: boolean;
    error?: string;
  };

  type RecoverDeviceResponse = {
    attempted: boolean;
    recovered: boolean;
    message: string;
    action: string;
  };

  const NOTIFICATION_DURATION_MS = 5000;

  let isRecording = $state(false);
  let startPending = $state(false);
  let preparePending = $state(false);
  let _status = $state('デバイス確認中...');
  let deviceState = $state<PreviewState>('checking');
  let deviceErrorMessage = $state('');
  let deviceStatusTimer: number | null = null;
  let isPrepared = $state(false);
  let isMetadataOpen = $state(false);
  let isRefreshingDeviceStatus = $state(false); // 多重実行防止フラグ
  let recoveryPending = $state(false);
  let hasTriedStartupRecovery = $state(false);
  let hasTriedIdleRecoveryForCurrentDisconnect = $state(false);
  let isCameraPermissionDialogOpen = $state(false);
  let isVideoFileInput = $state(false);
  let deviceStatusPollIntervalMs = getDeviceStatusPollIntervalMs('cpu');
  type MetadataValue = string | number | string[] | null | undefined;
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
    | 'special'
    | 'gold_medals'
    | 'silver_medals'
    | 'allies'
    | 'enemies';
  type BattleStatFieldKey = 'kill' | 'death' | 'special';
  type MetadataEventPayload = Partial<Record<MetadataFieldKey, MetadataValue>>;
  type MetadataNotification = {
    id: number;
    text: string;
    timer: number;
  };
  type MetadataFieldDescriptor = {
    key: MetadataFieldKey;
    label: string;
    format: (value: MetadataValue) => string | null;
    normalize?: (value: MetadataValue) => string | null;
  };
  const PLACEHOLDER_VALUES = new Set(['未取得', '']);
  const battleStatFieldKeys: BattleStatFieldKey[] = ['kill', 'death', 'special'];
  const startedAtFormatter = new Intl.DateTimeFormat('ja-JP', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
  let metadataOptionMap: ReturnType<typeof buildMetadataOptionMap> | null = null;
  const metadataFieldDescriptors: MetadataFieldDescriptor[] = [
    {
      key: 'game_mode',
      label: 'モード',
      format: (value) => formatEnumValue(value, metadataOptionMap?.gameModes ?? null),
    },
    {
      key: 'match',
      label: 'マッチタイプ',
      format: (value) => formatEnumValue(value, metadataOptionMap?.matches ?? null),
    },
    {
      key: 'rule',
      label: 'ルール',
      format: (value) => formatEnumValue(value, metadataOptionMap?.rules ?? null),
    },
    {
      key: 'stage',
      label: 'ステージ',
      format: (value) => formatEnumValue(value, metadataOptionMap?.stages ?? null),
    },
    {
      key: 'started_at',
      label: 'マッチング開始時間',
      format: formatStartedAtValue,
      normalize: normalizeStartedAtValue,
    },
    { key: 'rate', label: 'レート', format: formatTextValue },
    {
      key: 'judgement',
      label: '判定',
      format: (value) => formatEnumValue(value, metadataOptionMap?.judgements ?? null),
    },
  ];

  async function readApiErrorMessage(response: Response): Promise<string> {
    const responseClone = response.clone();
    try {
      const data = (await response.json()) as {
        detail?: string | { message?: string };
        message?: string;
      };
      if (typeof data?.detail === 'string') {
        return data.detail;
      }
      if (typeof data?.detail === 'object' && data?.detail?.message) {
        return data.detail.message;
      }
      if (typeof data?.message === 'string') {
        return data.message;
      }
    } catch {
      // ignore JSON parse errors
    }
    try {
      const text = await responseClone.text();
      if (text) {
        return text;
      }
    } catch {
      // ignore text read errors
    }
    return `status ${response.status}`;
  }
  let metadataNotifications = $state<MetadataNotification[]>([]);
  let notificationIdCounter = 0;
  let lastMetadata: Partial<Record<MetadataFieldKey, string>> = {};
  let pendingMetadataSessionReset = false;

  $effect(() => {
    const next = getDeviceStatusPollIntervalMs($renderMode);
    if (deviceStatusPollIntervalMs !== next) {
      deviceStatusPollIntervalMs = next;
      restartDeviceStatusPolling();
    }
  });

  function restartDeviceStatusPolling(): void {
    if (deviceStatusTimer !== null) {
      window.clearInterval(deviceStatusTimer);
      deviceStatusTimer = null;
    }
    if (isVideoFileInput || deviceState === 'connected') {
      return;
    }
    deviceStatusTimer = window.setInterval(() => {
      void refreshDeviceStatus();
    }, deviceStatusPollIntervalMs);
  }

  async function loadMetadataOptions(): Promise<void> {
    try {
      const options = await getMetadataOptions();
      metadataOptionMap = buildMetadataOptionMap(options);
    } catch (error) {
      console.error('Failed to load metadata options:', error);
    }
  }

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
    if (Array.isArray(value)) {
      const normalized = value.map((item) => item.trim()).filter((item) => item !== '');
      if (normalized.length === 0) {
        return null;
      }
      return normalized.join(' / ');
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

  function formatEnumValue(
    value: MetadataValue,
    optionMap: Record<string, string> | null
  ): string | null {
    const normalized = normalizeRawValue(value);
    if (normalized === null) {
      return null;
    }
    if (!optionMap) {
      return normalized;
    }
    return optionMap[normalized] ?? normalized;
  }

  function normalizeStoredMedalCount(value: string | undefined): number {
    if (!value) {
      return 0;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  function normalizeIncomingMedalCount(value: MetadataValue): number | null {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value === 'number') {
      return Number.isNaN(value) ? null : value;
    }
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (!trimmed) {
        return null;
      }
      const parsed = Number.parseInt(trimmed, 10);
      return Number.isNaN(parsed) ? null : parsed;
    }
    return null;
  }

  function formatMedalSummary(gold: number, silver: number): string {
    return `🥇x${gold} 🥈x${silver}`;
  }

  function normalizeStoredBattleStatCount(value: string | undefined): number | null {
    if (!value) {
      return null;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function formatBattleStatSummary(
    metadata: Partial<Record<MetadataFieldKey, string>>
  ): string | null {
    const kill = normalizeStoredBattleStatCount(metadata.kill);
    const death = normalizeStoredBattleStatCount(metadata.death);
    const special = normalizeStoredBattleStatCount(metadata.special);
    if (kill === null || death === null || special === null) {
      return null;
    }
    return `💀 ${kill}K/${death}D ✨SP×${special}`;
  }

  function normalizeWeaponSlots(value: MetadataValue): string[] | null {
    if (!Array.isArray(value)) {
      return null;
    }
    if (value.length === 0) {
      return null;
    }
    return value.map((item) => item.trim() || '不明');
  }

  function handleWeaponTeamMetadataUpdate(
    key: 'allies' | 'enemies',
    rawValue: MetadataValue,
    nextMetadata: Partial<Record<MetadataFieldKey, string>>,
    updates: string[]
  ): void {
    const normalizedSlots = normalizeWeaponSlots(rawValue);
    const previousValue = lastMetadata[key];

    console.log(`[handleMetadataUpdate] ${key}:`, {
      rawValue,
      normalizedSlots,
      previousValue,
    });

    if (normalizedSlots === null) {
      delete nextMetadata[key];
      return;
    }

    const normalizedTeam = normalizedSlots.join('|');
    nextMetadata[key] = normalizedTeam;
    if (previousValue === normalizedTeam) {
      console.log(`[handleMetadataUpdate] ${key}: 値が変わっていないためスキップ`);
      return;
    }

    const previousSlots = previousValue ? previousValue.split('|') : [];
    const teamLabel = key === 'allies' ? '味方' : '敵';
    const slotCount = Math.max(normalizedSlots.length, previousSlots.length);
    for (let index = 0; index < slotCount; index += 1) {
      const nextSlot = normalizedSlots[index] ?? '不明';
      const previousSlot = previousSlots[index];
      if (previousSlot === nextSlot) {
        continue;
      }
      updates.push(`${teamLabel}${index + 1}: ${nextSlot}`);
    }
  }

  function handleBattleStatMetadataUpdate(
    payload: MetadataEventPayload,
    nextMetadata: Partial<Record<MetadataFieldKey, string>>,
    updates: string[]
  ): void {
    let hasBattleStatChange = false;

    battleStatFieldKeys.forEach((key) => {
      if (!(key in payload)) {
        return;
      }

      const rawValue = payload[key];
      const normalizedForComparison = normalizeRawValue(rawValue);
      const previousValue = lastMetadata[key];

      console.log(`[handleMetadataUpdate] ${key}:`, {
        rawValue,
        normalizedForComparison,
        previousValue,
      });

      if (normalizedForComparison === null) {
        delete nextMetadata[key];
        if (previousValue !== undefined) {
          hasBattleStatChange = true;
        }
        return;
      }

      nextMetadata[key] = normalizedForComparison;
      if (previousValue !== normalizedForComparison) {
        hasBattleStatChange = true;
      }
    });

    if (!hasBattleStatChange) {
      return;
    }

    const formatted = formatBattleStatSummary(nextMetadata);
    if (formatted === null) {
      console.log('[handleMetadataUpdate] battle_stats: フォーマット結果がnullのためスキップ');
      return;
    }

    console.log(`[handleMetadataUpdate] battle_stats: 通知追加 - キルレ：${formatted}`);
    updates.push(`キルレ: ${formatted}`);
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

  function resetMetadataTracking(): void {
    lastMetadata = {};
    pendingMetadataSessionReset = false;
  }

  function prepareMetadataTrackingForNextSession(payload: MetadataEventPayload): void {
    if (!pendingMetadataSessionReset) {
      return;
    }

    const incomingStartedAt = normalizeStartedAtValue(payload.started_at);
    const previousStartedAt = lastMetadata.started_at;

    // 停止直後に同一セッションの最終メタデータが再送されるため、
    // started_at が同じ間は比較基準を維持する。
    if (incomingStartedAt !== null && incomingStartedAt === previousStartedAt) {
      return;
    }

    resetMetadataTracking();
  }

  function handleMetadataUpdate(payload: MetadataEventPayload): void {
    prepareMetadataTrackingForNextSession(payload);
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

    handleBattleStatMetadataUpdate(payload, nextMetadata, updates);

    if ('allies' in payload) {
      handleWeaponTeamMetadataUpdate('allies', payload.allies, nextMetadata, updates);
    }
    if ('enemies' in payload) {
      handleWeaponTeamMetadataUpdate('enemies', payload.enemies, nextMetadata, updates);
    }
    if ('gold_medals' in payload || 'silver_medals' in payload) {
      const previousGold = normalizeStoredMedalCount(lastMetadata.gold_medals);
      const previousSilver = normalizeStoredMedalCount(lastMetadata.silver_medals);
      const nextGold =
        'gold_medals' in payload
          ? (normalizeIncomingMedalCount(payload.gold_medals) ?? 0)
          : previousGold;
      const nextSilver =
        'silver_medals' in payload
          ? (normalizeIncomingMedalCount(payload.silver_medals) ?? 0)
          : previousSilver;

      nextMetadata.gold_medals = nextGold.toString();
      nextMetadata.silver_medals = nextSilver.toString();

      if (previousGold !== nextGold || previousSilver !== nextSilver) {
        updates.push(`表彰: ${formatMedalSummary(nextGold, nextSilver)}`);
      }
    }

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
      _status = '録画準備中 (OBS起動＆仮想カメラ有効化)...';
      const response = await fetch('/api/recorder/prepare', {
        method: 'POST',
      });
      if (!response.ok) {
        const message = await readApiErrorMessage(response);
        throw new Error(message);
      }
      const result = (await response.json()) as PrepareRecordingResponse;
      console.log('prepare_recording result:', result);
      if (result.success === true) {
        isPrepared = true;
        _status = '録画準備完了';
        console.log('録画準備完了 - isPrepared =', isPrepared);
      } else {
        _status = `録画準備エラー: ${result.error ?? '原因不明のエラー'}`;
        console.error('録画準備失敗:', result);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      _status = `録画準備エラー: ${message}`;
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
      _status = '自動録画機能 ON 準備中...';
      const response = await fetch('/api/recorder/enable-auto', {
        method: 'POST',
      });
      if (!response.ok) {
        const message = await readApiErrorMessage(response);
        throw new Error(message);
      }
      const result = (await response.json()) as StartRecordingResponse;
      console.log('enable_auto_recording result:', result);
      if (result.success) {
        _status = '自動録画機能 ON（バトル開始を検知中...）';
        console.log('自動録画機能 ON 成功');
        // 録画準備完了の通知を表示
        await notifyRecordingReady();
      } else {
        _status = `エラー: ${result.error ?? '原因不明のエラー'}`;
        console.error('自動録画有効化失敗:', result.error);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      _status = `エラー: ${message}`;
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
      _status = '自動録画機能 ON 準備中...';
      const response = await fetch('/api/recorder/start', {
        method: 'POST',
      });
      if (!response.ok) {
        const message = await readApiErrorMessage(response);
        throw new Error(message);
      }
      const result = (await response.json()) as StartRecordingResponse;
      console.log('start_recording result:', result);
      if (result.success) {
        isRecording = true;
        _status = '自動録画機能 ON';
        console.log('自動録画機能 ON 成功');
      } else {
        _status = `エラー: ${result.error ?? '原因不明のエラー'}`;
        console.error('自動録画開始失敗:', result.error);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      _status = `エラー: ${message}`;
      console.error('自動録画開始エラー:', error);
    } finally {
      startPending = false;
    }
  }

  function canAutoRecover(): boolean {
    return (
      !isVideoFileInput && !isRecording && !startPending && !preparePending && !recoveryPending
    );
  }

  async function attemptDeviceRecovery(
    trigger: 'manual' | 'startup_auto' | 'idle_auto'
  ): Promise<RecoverDeviceResponse | null> {
    if (recoveryPending) {
      return null;
    }

    recoveryPending = true;
    try {
      _status =
        trigger === 'manual'
          ? 'キャプチャーデバイスの復旧を試しています...'
          : 'キャプチャーデバイスの自動復旧を試しています...';
      const result = (await recoverCaptureDevice(trigger)) as RecoverDeviceResponse;
      if (result.recovered) {
        _status = 'キャプチャーデバイスを復旧しました。再確認中...';
        await refreshDeviceStatus();
      } else {
        _status = `復旧できませんでした: ${result.message}`;
      }
      return result;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '原因不明のエラー';
      _status = `復旧エラー: ${message}`;
      console.error('キャプチャーデバイス復旧エラー:', error);
      return null;
    } finally {
      recoveryPending = false;
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

  async function refreshPreviewMode(): Promise<void> {
    try {
      const nextIsVideoFileInput = (await getRecorderPreviewMode()) === 'video_file';
      const previewModeChanged = isVideoFileInput !== nextIsVideoFileInput;
      isVideoFileInput = nextIsVideoFileInput;
      if (isVideoFileInput) {
        isCameraPermissionDialogOpen = false;
      }
      if (previewModeChanged) {
        restartDeviceStatusPolling();
      }
    } catch (error) {
      console.error('Failed to refresh preview mode:', error);
    }
  }

  async function checkAndShowCameraPermissionDialog(): Promise<void> {
    try {
      isVideoFileInput = (await getRecorderPreviewMode()) === 'video_file';
      if (isVideoFileInput) {
        return;
      }

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
    const wasRecording = isRecording;
    const wasStartPending = startPending;
    const wasPreparePending = preparePending;
    deviceState = nextState;

    if (nextState === 'error') {
      deviceErrorMessage = message;
      const details = message ? ` (${message})` : '';
      _status = `エラー: キャプチャーデバイスの状態を取得できません${details}`;
      return;
    }

    deviceErrorMessage = '';

    if (nextState === 'connected' && previous !== 'connected') {
      hasTriedIdleRecoveryForCurrentDisconnect = false;
      if (deviceStatusTimer !== null) {
        window.clearInterval(deviceStatusTimer);
        deviceStatusTimer = null;
      }
      console.log('デバイス接続を検出 - 録画準備を開始');
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
      _status = recoveryPending
        ? 'キャプチャーデバイスを復旧しています...'
        : 'キャプチャーデバイスを接続してください';
      if (
        previous === 'connected' &&
        !hasTriedIdleRecoveryForCurrentDisconnect &&
        !wasRecording &&
        !wasStartPending &&
        !wasPreparePending &&
        canAutoRecover()
      ) {
        hasTriedIdleRecoveryForCurrentDisconnect = true;
        void attemptDeviceRecovery('idle_auto');
      }
      return;
    }

    if (nextState === 'checking' && !isRecording && !startPending && !preparePending) {
      _status = 'デバイス確認中...';
    }
  }

  onMount(() => {
    void loadMetadataOptions();
    void (async () => {
      await refreshPreviewMode();
      await refreshDeviceStatus();
      if (!hasTriedStartupRecovery && deviceState === 'disconnected' && canAutoRecover()) {
        hasTriedStartupRecovery = true;
        await attemptDeviceRecovery('startup_auto');
      }
    })();
    restartDeviceStatusPolling();

    // ドメインイベントを購読
    const domainEventSource = subscribeDomainEvents((event: DomainEvent) => {
      if (
        event.type === 'domain.recording.started' ||
        event.type === 'domain.recording.resumed' ||
        event.type === 'domain.recording.paused'
      ) {
        isRecording = true;
        console.log('[DomainEvent] recording session active', event.type);
        return;
      }
      if (event.type === 'domain.recording.metadata_updated') {
        const payload = event.payload as { metadata?: MetadataEventPayload };
        if (payload?.metadata) {
          handleMetadataUpdate(payload.metadata);
        }
        return;
      }
      if (
        event.type === 'domain.recording.stopped' ||
        event.type === 'domain.recording.cancelled'
      ) {
        isRecording = false;
        pendingMetadataSessionReset = true;
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

<div
  class="preview-container glass-surface"
  data-testid="preview-container"
  data-device-state={deviceState}
>
  {#if deviceState === 'connected'}
    <div class="metadata-button-container">
      <button
        class="metadata-toggle-btn glass-icon-button"
        type="button"
        onclick={toggleMetadata}
        aria-label={isMetadataOpen ? 'メタデータを閉じる' : 'メタデータを表示'}
        title={isMetadataOpen ? 'メタデータを閉じる' : 'メタデータを表示'}
        data-testid="metadata-toggle-button"
      >
        {#if isMetadataOpen}
          <X class="icon" aria-hidden="true" stroke-width={1.75} />
        {:else}
          <Info class="icon" aria-hidden="true" stroke-width={1.75} />
        {/if}
      </button>
      {#if !isMetadataOpen && metadataNotifications.length > 0}
        <div class="metadata-notifications" data-testid="metadata-notifications">
          {#each metadataNotifications as notification (notification.id)}
            <div class="metadata-notification glass-pill" data-testid="metadata-notification">
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

  {#if deviceState === 'disconnected' || deviceState === 'error'}
    <div class="recovery-actions">
      <button
        class="recovery-button glass-pill"
        type="button"
        onclick={() => void attemptDeviceRecovery('manual')}
        disabled={recoveryPending}
      >
        {recoveryPending ? '復旧中...' : '復旧を試す'}
      </button>
    </div>
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
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.04);
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

  .recovery-actions {
    position: absolute;
    right: 1rem;
    bottom: 1rem;
    z-index: 220;
  }

  .recovery-button {
    border: 1px solid rgba(var(--theme-rgb-accent), 0.45);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.96) 0%,
      rgba(var(--theme-rgb-accent-bright), 0.92) 100%
    );
    color: var(--theme-accent-ink-surface);
    font-weight: 700;
    padding: 0.7rem 1.05rem;
    cursor: pointer;
    transition:
      transform 0.2s ease,
      box-shadow 0.2s ease,
      opacity 0.2s ease;
  }

  .recovery-button:hover:enabled {
    transform: translateY(-1px);
    box-shadow:
      0 10px 22px rgba(var(--theme-rgb-accent), 0.28),
      0 0 12px rgba(var(--theme-rgb-accent), 0.16);
  }

  .recovery-button:disabled {
    cursor: wait;
    opacity: 0.72;
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
      0 7px 18px rgba(var(--theme-rgb-black), 0.24),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.12);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    box-sizing: border-box;
    transition:
      border-color 0.2s ease,
      background 0.2s ease,
      box-shadow 0.2s ease;
  }

  .metadata-toggle-btn:hover {
    border-color: rgba(var(--theme-rgb-accent), 0.45);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.12) 0%,
      rgba(var(--theme-rgb-white), 0.04) 100%
    );
    box-shadow:
      0 10px 22px rgba(var(--theme-rgb-black), 0.28),
      0 0 12px rgba(var(--theme-rgb-accent), 0.14);
  }

  .metadata-toggle-btn:focus-visible {
    outline: none;
    border-color: rgba(var(--theme-rgb-accent), 0.55);
    box-shadow:
      0 0 0 3px rgba(var(--theme-rgb-ring-strong), 0.9),
      0 0 0 6px rgba(var(--theme-rgb-accent), 0.28),
      0 12px 24px rgba(var(--theme-rgb-accent), 0.2);
  }

  .metadata-toggle-btn:active {
    box-shadow:
      0 5px 12px rgba(var(--theme-rgb-black), 0.24),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.18);
  }

  .metadata-notifications {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    width: 100%;
  }

  .metadata-notification {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 1) 0%,
      rgba(var(--theme-rgb-accent-bright), 0.98) 100%
    );
    backdrop-filter: blur(8px) saturate(145%);
    -webkit-backdrop-filter: blur(8px) saturate(145%);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.8);
    border-radius: 999px;
    padding: 0.55rem 1rem;
    color: var(--theme-accent-ink-surface);
    font-size: 0.85rem;
    font-weight: 700;
    white-space: nowrap;
    max-width: 250px;
    overflow: hidden;
    text-overflow: ellipsis;
    box-shadow:
      0 8px 18px rgba(var(--theme-rgb-accent), 0.3),
      0 0 12px rgba(var(--theme-rgb-accent), 0.18),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.3);
  }
</style>
