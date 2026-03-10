<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { slide } from 'svelte/transition';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import MetadataForm from './MetadataForm.svelte';
  import { subscribeDomainEvents, type DomainEvent } from '../../domainEvents';
  import { getMetadataOptions } from '../../api/metadata';
  import type { MetadataOptionItem } from '../../api/types';
  import { createEmptyEditableMetadata, type EditableMetadata } from '../../metadata/editable';
  import {
    applyIncomingLiveMetadata,
    createEmptyLiveMetadataState,
    createEmptyLiveManualEditState,
    buildLiveMetadataPayload,
    toEditableLiveMetadata,
    toLiveMetadataState,
    type LiveManualEditState,
    type LiveMetadataPayload,
    type LiveMetadataState,
  } from '../../metadata/live';

  export let visible: boolean = false;
  let showAlertDialog = false; // アラートダイアログ表示フラグ
  let alertMessage = ''; // アラートメッセージ
  let alertVariant: 'info' | 'success' | 'warning' | 'error' = 'info';

  // SSE接続
  let domainEventSource: EventSource | null = null;

  // メタデータ (SSE経由で更新)
  let metadata: LiveMetadataState = createEmptyLiveMetadataState();
  let editableMetadata: EditableMetadata = createEmptyEditableMetadata();

  // 手動編集フラグ (各フィールドごと)
  let manuallyEdited: LiveManualEditState = createEmptyLiveManualEditState();

  const placeholderLabel = {
    gameMode: '未取得',
    match: '未取得',
    rule: '未取得',
    stage: '未取得',
    rate: '未検出',
    judgement: '未判定',
    startedAt: '未開始',
  };
  let gameModeOptions: MetadataOptionItem[] = [];
  let matchOptions: MetadataOptionItem[] = [];
  let ruleOptions: MetadataOptionItem[] = [];
  let stageOptions: MetadataOptionItem[] = [];
  let judgementOptions: MetadataOptionItem[] = [];
  const editableFieldToLiveField: Record<keyof EditableMetadata, keyof LiveMetadataState> = {
    gameMode: 'game_mode',
    startedAt: 'started_at',
    match: 'match',
    rule: 'rule',
    stage: 'stage',
    rate: 'rate',
    judgement: 'judgement',
    kill: 'kill',
    death: 'death',
    special: 'special',
    goldMedals: 'gold_medals',
    silverMedals: 'silver_medals',
    allies: 'allies',
    enemies: 'enemies',
  };

  let hasLoadedInitial = false;

  async function loadMetadataOptions(): Promise<void> {
    try {
      const options = await getMetadataOptions();
      gameModeOptions = options.gameModes;
      matchOptions = options.matches;
      ruleOptions = options.rules;
      stageOptions = options.stages;
      judgementOptions = options.judgements;
    } catch (error) {
      console.error('Failed to load metadata options:', error);
    }
  }

  function setNow(): void {
    const now = new Date();
    editableMetadata = {
      ...editableMetadata,
      startedAt: now.toISOString().replace('T', ' ').substring(0, 19),
    };
    metadata = toLiveMetadataState(editableMetadata);
    markEdited('started_at');
  }

  // 各フィールドの手動編集をマーク
  function markEdited(field: keyof LiveMetadataState): void {
    manuallyEdited = {
      ...manuallyEdited,
      [field]: true,
    };
    console.log(`フィールド "${field}" が手動編集されました`);
    console.log('手動編集フラグの状態:', manuallyEdited);
  }

  function handleFieldEdited(field: keyof EditableMetadata): void {
    metadata = toLiveMetadataState(editableMetadata);
    markEdited(editableFieldToLiveField[field]);
  }

  async function fetchCurrentMetadata(): Promise<void> {
    try {
      const response = await fetch('/api/recorder/metadata');
      if (!response.ok) {
        console.error('Failed to fetch metadata:', response.status);
        return;
      }
      const data = await response.json();
      console.log('Fetched current metadata:', data);
      updateMetadata(data);
      hasLoadedInitial = true;
    } catch (error) {
      console.error('Failed to fetch current metadata:', error);
    }
  }

  function updateMetadata(data: LiveMetadataPayload): void {
    // 手動編集されていないフィールドのみ更新
    console.log('メタデータ自動更新を試行:', data);
    const result = applyIncomingLiveMetadata(metadata, manuallyEdited, data);
    metadata = result.metadata;
    editableMetadata = toEditableLiveMetadata(result.metadata);
    const { updatedFields, skippedFields } = result;

    if (updatedFields.length > 0) {
      console.log('✓ 自動更新されたフィールド:', updatedFields);
    }
    if (skippedFields.length > 0) {
      console.log('⊗ スキップされたフィールド:', skippedFields);
    }
  }

  function resetManualEdits(): void {
    // すべての手動編集フラグをクリア
    console.log('手動編集フラグをすべてリセット');
    manuallyEdited = createEmptyLiveManualEditState();
  }

  function resetMetadata(): void {
    // メタデータを初期状態にリセット
    console.log('メタデータをリセット');
    metadata = createEmptyLiveMetadataState();
    editableMetadata = toEditableLiveMetadata(metadata);
  }

  function handleReset(): void {
    resetManualEdits();
    hasLoadedInitial = false;
    void fetchCurrentMetadata();
  }

  async function saveMetadata(): Promise<void> {
    try {
      const payload = buildLiveMetadataPayload(metadata, manuallyEdited);
      if (Object.keys(payload).length === 0) {
        alertMessage = '更新対象がありません';
        alertVariant = 'info';
        showAlertDialog = true;
        return;
      }
      const response = await fetch('/api/recorder/metadata', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        console.error('Failed to save metadata:', response.status);
        alertMessage = 'メタデータの保存に失敗しました';
        alertVariant = 'error';
        showAlertDialog = true;
        return;
      }

      const result = await response.json();
      console.log('Metadata saved:', result);
      alertMessage = 'メタデータを保存しました';
      alertVariant = 'success';
      showAlertDialog = true;
    } catch (error) {
      console.error('Failed to save metadata:', error);
      alertMessage = 'メタデータの保存に失敗しました';
      alertVariant = 'error';
      showAlertDialog = true;
    }
  }

  function connectSSE(): void {
    domainEventSource?.close();
    domainEventSource = subscribeDomainEvents((event: DomainEvent) => {
      if (event.type === 'domain.recording.metadata_updated') {
        const payload = event.payload as { metadata?: LiveMetadataPayload };
        if (payload?.metadata) {
          updateMetadata(payload.metadata);
        }
        return;
      }
      if (
        event.type === 'domain.recording.stopped' ||
        event.type === 'domain.recording.cancelled'
      ) {
        console.log('Recording stopped - resetting manual edits and metadata');
        resetManualEdits();
        resetMetadata();
        hasLoadedInitial = false;
      }
    });

    domainEventSource.onerror = () => {
      console.error('Domain event SSE connection error');
      domainEventSource?.close();
      setTimeout(() => {
        if (domainEventSource?.readyState === EventSource.CLOSED) {
          connectSSE();
        }
      }, 5000);
    };
  }

  // visibleが変更されたときに初期データを取得
  $: if (visible && !hasLoadedInitial) {
    fetchCurrentMetadata();
  }

  onMount(() => {
    loadMetadataOptions();
    connectSSE();
  });

  onDestroy(() => {
    domainEventSource?.close();
  });
</script>

<!-- アラートダイアログ -->
<NotificationDialog
  isOpen={showAlertDialog}
  variant={alertVariant}
  message={alertMessage}
  on:close={() => (showAlertDialog = false)}
/>

{#if visible}
  <div class="overlay" transition:slide={{ duration: 300, axis: 'x' }}>
    <div class="panel">
      <div class="panel-content glass-scroller">
        <MetadataForm
          bind:metadata={editableMetadata}
          variant="overlay"
          showGameMode={true}
          {gameModeOptions}
          {matchOptions}
          {ruleOptions}
          {stageOptions}
          {judgementOptions}
          placeholderLabels={placeholderLabel}
          startedAtActionText="Now"
          onStartedAtAction={setNow}
          onFieldEdited={handleFieldEdited}
        />
      </div>

      <div class="panel-footer">
        <button type="button" class="reset-btn" on:click={handleReset}>リセット</button>
        <button type="button" class="save-btn" on:click={saveMetadata}>保存</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: absolute;
    top: 8px;
    right: 8px;
    bottom: 8px;
    width: 320px;
    background: var(--glass-bg-strong);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    z-index: 100;
    overflow-y: auto;
    border: 1px solid var(--glass-border);
    border-left-color: rgba(var(--theme-rgb-accent), 0.35);
    border-top-right-radius: calc(var(--glass-radius) + 6px);
    border-bottom-right-radius: calc(var(--glass-radius) + 6px);
    box-shadow:
      -8px 0 32px rgba(var(--theme-rgb-black), 0.45),
      0 0 0 1px rgba(var(--theme-rgb-white), 0.04) inset,
      0 0 60px rgba(var(--theme-rgb-accent), 0.12);
  }

  .panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .panel-content {
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    flex: 1;
    overflow-y: auto;
    border-radius: calc(var(--glass-radius) - 4px);
  }

  .panel-footer {
    padding: 1rem 1.25rem;
    border-top: 1px solid rgba(var(--theme-rgb-accent), 0.18);
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
    background: linear-gradient(
      180deg,
      rgba(var(--theme-rgb-surface-card-dark-2), 0.82) 0%,
      rgba(var(--theme-rgb-surface-card-dark), 0.72) 100%
    );
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom-right-radius: calc(var(--glass-radius) + 6px);
  }

  .reset-btn,
  .save-btn {
    padding: 0.65rem 1.3rem;
    border: none;
    border-radius: 999px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    letter-spacing: 0.03em;
  }

  .reset-btn::before,
  .save-btn::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    border-radius: 50%;
    background: rgba(var(--theme-rgb-white), 0.2);
    transform: translate(-50%, -50%);
    transition:
      width 0.6s ease,
      height 0.6s ease;
  }

  .reset-btn:hover::before,
  .save-btn:hover::before {
    width: 300px;
    height: 300px;
  }

  .reset-btn {
    background: linear-gradient(
      145deg,
      rgba(var(--theme-rgb-white), 0.12) 0%,
      rgba(var(--theme-rgb-white), 0.06) 100%
    );
    color: var(--text-primary);
    border: 1px solid rgba(var(--theme-rgb-white), 0.2);
    box-shadow:
      0 14px 28px rgba(var(--theme-rgb-black), 0.2),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.25);
  }

  .reset-btn:hover {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.22) 0%,
      rgba(var(--theme-rgb-white), 0.12) 100%
    );
    border-color: rgba(var(--theme-rgb-white), 0.3);
    transform: translateY(-2px);
    box-shadow:
      0 20px 36px rgba(var(--theme-rgb-black), 0.25),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.2);
  }

  .save-btn {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.95) 0%,
      rgba(var(--theme-rgb-accent-strong), 0.85) 100%
    );
    color: var(--theme-accent-ink-surface);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.55);
    font-weight: 700;
    box-shadow:
      0 18px 36px rgba(var(--theme-rgb-accent), 0.4),
      0 0 32px rgba(var(--theme-rgb-accent), 0.3),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.25);
  }

  .save-btn:hover {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 1) 0%,
      rgba(var(--theme-rgb-accent-strong), 0.92) 100%
    );
    border-color: rgba(var(--theme-rgb-accent), 0.7);
    transform: translateY(-2px);
    box-shadow:
      0 24px 44px rgba(var(--theme-rgb-accent), 0.5),
      0 0 40px rgba(var(--theme-rgb-accent), 0.4),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.3);
  }

  .save-btn:active {
    transform: translateY(0);
    box-shadow:
      0 2px 8px rgba(var(--theme-rgb-accent), 0.3),
      0 0 16px rgba(var(--theme-rgb-accent), 0.2),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.2);
  }

  /* スクロールバーのスタイリング */
  .panel-content::-webkit-scrollbar {
    width: 8px;
  }

  .panel-content::-webkit-scrollbar-track {
    background: rgba(var(--theme-rgb-white), 0.05);
    border-radius: 4px;
  }

  .panel-content::-webkit-scrollbar-thumb {
    background: rgba(var(--theme-rgb-accent), 0.3);
    border-radius: 4px;
  }

  .panel-content::-webkit-scrollbar-thumb:hover {
    background: rgba(var(--theme-rgb-accent), 0.5);
  }
</style>
