<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { slide } from 'svelte/transition';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import { subscribeDomainEvents, type DomainEvent } from '../../domainEvents';
  import { getMetadataOptions } from '../../api/metadata';
  import type { MetadataOptionItem } from '../../api/types';

  export let visible: boolean = false;
  let showAlertDialog = false; // アラートダイアログ表示フラグ
  let alertMessage = ''; // アラートメッセージ
  let alertVariant: 'info' | 'success' | 'warning' | 'error' = 'info';

  type MetadataPayload = {
    game_mode?: string;
    stage?: string;
    started_at?: string;
    match?: string;
    rule?: string;
    rate?: string;
    judgement?: string;
    kill?: number;
    death?: number;
    special?: number;
    hazard?: number;
    golden_egg?: number;
    power_egg?: number;
    rescue?: number;
    rescued?: number;
  };

  // SSE接続
  let domainEventSource: EventSource | null = null;

  // メタデータ (SSE経由で更新)
  let metadata = {
    game_mode: '',
    started_at: '',
    match: '',
    rule: '',
    rate: '',
    judgement: '',
    stage: '',
    kill: 0,
    death: 0,
    special: 0,
  };

  // 手動編集フラグ (各フィールドごと)
  let manuallyEdited = {
    game_mode: false,
    started_at: false,
    match: false,
    rule: false,
    rate: false,
    judgement: false,
    stage: false,
    kill: false,
    death: false,
    special: false,
  };

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

  let _eventSource: EventSource | null = null;
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
    metadata.started_at = now.toISOString().replace('T', ' ').substring(0, 19);
    manuallyEdited.started_at = true;
  }

  // 各フィールドの手動編集をマーク
  function markEdited(field: keyof typeof metadata): void {
    manuallyEdited[field] = true;
    console.log(`フィールド "${field}" が手動編集されました`);
    console.log('手動編集フラグの状態:', manuallyEdited);
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

  function updateMetadata(data: MetadataPayload): void {
    // 手動編集されていないフィールドのみ更新
    console.log('メタデータ自動更新を試行:', data);
    let updatedFields: string[] = [];
    let skippedFields: string[] = [];

    if (!manuallyEdited.game_mode) {
      metadata.game_mode = data.game_mode ?? '';
      updatedFields.push('game_mode');
    } else {
      skippedFields.push('game_mode (手動編集済み)');
    }
    if (!manuallyEdited.started_at) {
      metadata.started_at = data.started_at ?? '';
      updatedFields.push('started_at');
    } else {
      skippedFields.push('started_at (手動編集済み)');
    }
    if (!manuallyEdited.match) {
      metadata.match = data.match ?? '';
      updatedFields.push('match');
    } else {
      skippedFields.push('match (手動編集済み)');
    }
    if (!manuallyEdited.rule) {
      metadata.rule = data.rule ?? '';
      updatedFields.push('rule');
    } else {
      skippedFields.push('rule (手動編集済み)');
    }
    if (!manuallyEdited.rate) {
      metadata.rate = data.rate ?? '';
      updatedFields.push('rate');
    } else {
      skippedFields.push('rate (手動編集済み)');
    }
    if (!manuallyEdited.judgement) {
      metadata.judgement = data.judgement ?? '';
      updatedFields.push('judgement');
    } else {
      skippedFields.push('judgement (手動編集済み)');
    }
    if (!manuallyEdited.stage) {
      metadata.stage = data.stage ?? '';
      updatedFields.push('stage');
    } else {
      skippedFields.push('stage (手動編集済み)');
    }
    if (!manuallyEdited.kill) {
      metadata.kill = data.kill ?? 0;
      updatedFields.push('kill');
    } else {
      skippedFields.push('kill (手動編集済み)');
    }
    if (!manuallyEdited.death) {
      metadata.death = data.death ?? 0;
      updatedFields.push('death');
    } else {
      skippedFields.push('death (手動編集済み)');
    }
    if (!manuallyEdited.special) {
      metadata.special = data.special ?? 0;
      updatedFields.push('special');
    } else {
      skippedFields.push('special (手動編集済み)');
    }

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
    manuallyEdited = {
      game_mode: false,
      started_at: false,
      match: false,
      rule: false,
      rate: false,
      judgement: false,
      stage: false,
      kill: false,
      death: false,
      special: false,
    };
  }

  function resetMetadata(): void {
    // メタデータを初期状態にリセット
    console.log('メタデータをリセット');
    metadata = {
      game_mode: '',
      started_at: '',
      match: '',
      rule: '',
      rate: '',
      judgement: '',
      stage: '',
      kill: 0,
      death: 0,
      special: 0,
    };
  }

  async function saveMetadata(): Promise<void> {
    try {
      const payload: Record<string, string | number> = {};
      if (manuallyEdited.game_mode && metadata.game_mode) {
        payload.game_mode = metadata.game_mode;
      }
      if (manuallyEdited.started_at && metadata.started_at) {
        payload.started_at = metadata.started_at;
      }
      if (manuallyEdited.match && metadata.match) {
        payload.match = metadata.match;
      }
      if (manuallyEdited.rule && metadata.rule) {
        payload.rule = metadata.rule;
      }
      if (manuallyEdited.rate && metadata.rate) {
        payload.rate = metadata.rate;
      }
      if (manuallyEdited.judgement && metadata.judgement) {
        payload.judgement = metadata.judgement;
      }
      if (manuallyEdited.stage && metadata.stage) {
        payload.stage = metadata.stage;
      }
      if (manuallyEdited.kill && metadata.kill !== null && metadata.kill !== undefined) {
        payload.kill = metadata.kill;
      }
      if (manuallyEdited.death && metadata.death !== null && metadata.death !== undefined) {
        payload.death = metadata.death;
      }
      if (manuallyEdited.special && metadata.special !== null && metadata.special !== undefined) {
        payload.special = metadata.special;
      }
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
        const payload = event.payload as { metadata?: MetadataPayload };
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
        <div class="field-group">
          <label for="game_mode">ゲームモード</label>
          <select
            id="game_mode"
            bind:value={metadata.game_mode}
            on:change={() => markEdited('game_mode')}
          >
            <option value="">{placeholderLabel.gameMode}</option>
            {#each gameModeOptions as mode}
              <option value={mode.key}>{mode.label}</option>
            {/each}
          </select>
        </div>

        <div class="field-group">
          <label for="started_at">マッチング開始</label>
          <div class="datetime-field">
            <input
              id="started_at"
              type="text"
              bind:value={metadata.started_at}
              on:input={() => markEdited('started_at')}
              placeholder={placeholderLabel.startedAt}
            />
            <button type="button" class="now-btn" on:click={setNow}>Now</button>
          </div>
        </div>

        <div class="field-group">
          <label for="match">マッチタイプ</label>
          <select id="match" bind:value={metadata.match} on:change={() => markEdited('match')}>
            <option value="">{placeholderLabel.match}</option>
            {#each matchOptions as match}
              <option value={match.key}>{match.label}</option>
            {/each}
          </select>
        </div>

        <div class="field-group">
          <label for="rule">ルール</label>
          <select id="rule" bind:value={metadata.rule} on:change={() => markEdited('rule')}>
            <option value="">{placeholderLabel.rule}</option>
            {#each ruleOptions as rule}
              <option value={rule.key}>{rule.label}</option>
            {/each}
          </select>
        </div>

        <div class="field-group">
          <label for="rate">レート</label>
          <input
            id="rate"
            type="text"
            bind:value={metadata.rate}
            on:input={() => markEdited('rate')}
            placeholder={placeholderLabel.rate}
          />
        </div>

        <div class="field-group">
          <label for="judgement">判定</label>
          <select
            id="judgement"
            bind:value={metadata.judgement}
            on:change={() => markEdited('judgement')}
          >
            <option value="">{placeholderLabel.judgement}</option>
            {#each judgementOptions as judgement}
              <option value={judgement.key}>{judgement.label}</option>
            {/each}
          </select>
        </div>

        <div class="field-group">
          <label for="stage">ステージ</label>
          <select id="stage" bind:value={metadata.stage} on:change={() => markEdited('stage')}>
            <option value="">{placeholderLabel.stage}</option>
            {#each stageOptions as stage}
              <option value={stage.key}>{stage.label}</option>
            {/each}
          </select>
        </div>

        <div class="stats-row">
          <div class="field-group">
            <label for="kill">キル数</label>
            <input
              id="kill"
              type="number"
              bind:value={metadata.kill}
              on:input={() => markEdited('kill')}
              min="0"
            />
          </div>

          <div class="field-group">
            <label for="death">デス数</label>
            <input
              id="death"
              type="number"
              bind:value={metadata.death}
              on:input={() => markEdited('death')}
              min="0"
            />
          </div>

          <div class="field-group">
            <label for="special">SP</label>
            <input
              id="special"
              type="number"
              bind:value={metadata.special}
              on:input={() => markEdited('special')}
              min="0"
            />
          </div>
        </div>
      </div>

      <div class="panel-footer">
        <button type="button" class="reset-btn">リセット</button>
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
    border-left-color: rgba(25, 211, 199, 0.35);
    border-top-right-radius: calc(var(--glass-radius) + 6px);
    border-bottom-right-radius: calc(var(--glass-radius) + 6px);
    box-shadow:
      -8px 0 32px rgba(0, 0, 0, 0.45),
      0 0 0 1px rgba(255, 255, 255, 0.04) inset,
      0 0 60px rgba(25, 211, 199, 0.12);
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

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .field-group label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--accent-color);
    text-align: left;
    letter-spacing: 0.02em;
  }

  .field-group input,
  .field-group select {
    padding: 0.55rem 0.85rem;
    border-radius: calc(var(--glass-radius) - 8px);
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: linear-gradient(145deg, rgba(4, 12, 24, 0.75) 0%, rgba(8, 18, 30, 0.68) 100%);
    color: var(--text-primary);
    font-size: 0.875rem;
    transition: all 0.25s ease;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.06),
      0 1px 12px rgba(0, 0, 0, 0.25);
  }

  /* selectのドロップダウンリスト */
  .field-group select option {
    background: #1a1a2e;
    color: #fff;
    padding: 0.5rem;
  }

  /* selectのカスタム矢印 */
  .field-group select {
    cursor: pointer;
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
    background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.7)' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
    background-size: 1rem;
    padding-right: 2.5rem;
  }

  .field-group input:focus,
  .field-group select:focus {
    outline: none;
    border-color: rgba(25, 211, 199, 0.55);
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.22) 0%, rgba(25, 211, 199, 0.08) 100%);
    box-shadow:
      0 0 0 2px rgba(3, 12, 20, 0.75),
      0 0 0 4px rgba(25, 211, 199, 0.2),
      0 12px 24px rgba(25, 211, 199, 0.18),
      inset 0 1px 3px rgba(0, 0, 0, 0.12);
  }

  .field-group input:hover,
  .field-group select:hover {
    border-color: rgba(255, 255, 255, 0.22);
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.06) 100%
    );
  }

  .field-group input::placeholder {
    color: rgba(255, 255, 255, 0.45);
  }

  .datetime-field {
    display: flex;
    gap: 0.5rem;
  }

  .datetime-field input {
    flex: 1;
  }

  .now-btn {
    padding: 0.5rem 1rem;
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.24) 0%, rgba(25, 211, 199, 0.14) 100%);
    border: 1px solid rgba(25, 211, 199, 0.45);
    border-radius: 999px;
    color: var(--accent-color);
    font-size: 0.8125rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    white-space: nowrap;
    position: relative;
    overflow: hidden;
    box-shadow:
      0 6px 18px rgba(25, 211, 199, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.18);
  }

  .now-btn::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.15);
    transform: translate(-50%, -50%);
    transition:
      width 0.5s ease,
      height 0.5s ease;
  }

  .now-btn:hover::before {
    width: 200px;
    height: 200px;
  }

  .now-btn:hover {
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.38) 0%, rgba(25, 211, 199, 0.24) 100%);
    border-color: rgba(25, 211, 199, 0.6);
    transform: translateY(-2px);
    box-shadow:
      0 6px 18px rgba(25, 211, 199, 0.28),
      0 0 20px rgba(25, 211, 199, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
  }

  .stats-row .field-group {
    min-width: 0;
  }

  .stats-row input {
    text-align: center;
    width: 100%;
  }

  .panel-footer {
    padding: 1rem 1.25rem;
    border-top: 1px solid rgba(25, 211, 199, 0.18);
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
    background: linear-gradient(180deg, rgba(6, 12, 18, 0.82) 0%, rgba(6, 12, 22, 0.72) 100%);
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
    background: rgba(255, 255, 255, 0.2);
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
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.06) 100%
    );
    color: var(--text-primary);
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow:
      0 14px 28px rgba(0, 0, 0, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }

  .reset-btn:hover {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.22) 0%,
      rgba(255, 255, 255, 0.12) 100%
    );
    border-color: rgba(255, 255, 255, 0.3);
    transform: translateY(-2px);
    box-shadow:
      0 20px 36px rgba(0, 0, 0, 0.25),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }

  .save-btn {
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.95) 0%, rgba(18, 145, 137, 0.85) 100%);
    color: #021015;
    border: 1px solid rgba(25, 211, 199, 0.55);
    font-weight: 700;
    box-shadow:
      0 18px 36px rgba(25, 211, 199, 0.4),
      0 0 32px rgba(25, 211, 199, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }

  .save-btn:hover {
    background: linear-gradient(135deg, rgba(25, 211, 199, 1) 0%, rgba(18, 145, 137, 0.92) 100%);
    border-color: rgba(25, 211, 199, 0.7);
    transform: translateY(-2px);
    box-shadow:
      0 24px 44px rgba(25, 211, 199, 0.5),
      0 0 40px rgba(25, 211, 199, 0.4),
      inset 0 1px 0 rgba(255, 255, 255, 0.3);
  }

  .save-btn:active {
    transform: translateY(0);
    box-shadow:
      0 2px 8px rgba(25, 211, 199, 0.3),
      0 0 16px rgba(25, 211, 199, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }

  /* スクロールバーのスタイリング */
  .panel-content::-webkit-scrollbar {
    width: 8px;
  }

  .panel-content::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
  }

  .panel-content::-webkit-scrollbar-thumb {
    background: rgba(25, 211, 199, 0.3);
    border-radius: 4px;
  }

  .panel-content::-webkit-scrollbar-thumb:hover {
    background: rgba(25, 211, 199, 0.5);
  }
</style>
