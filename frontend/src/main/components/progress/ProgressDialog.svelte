<script lang="ts">
  import { onDestroy } from 'svelte';
  import { fetchEditUploadStatus, updateEditUploadProcessOptions } from '../../api/assets';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import type { EditUploadStatus, ProgressEvent } from '../../api/types';
  import { Circle, Loader2, CheckCircle2, XCircle } from 'lucide-svelte';
  import { ProgressStateMachine, type ConnectionState } from './progressStateMachine';

  interface Props {
    isOpen?: boolean;
  }

  let { isOpen = $bindable(false) }: Props = $props();

  const sm = new ProgressStateMachine();
  let tasksVersion = $state(0);

  let eventSource: EventSource | null = null;
  let messageHandler: ((event: MessageEvent) => void) | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let countdownTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectAttempt = $state(0);
  let retryCountdown = $state(0);

  let connectionState = $state<ConnectionState>('idle');
  let editUploadStatus = $state<EditUploadStatus | null>(null);
  let optionLoading = $state(false);
  let optionSaving = $state(false);
  let optionErrorMessage = $state('');
  let wasOpen = $state(false);
  let statusRequestId = $state(0);

  const dialogMinHeight = 'min(70vh, 46rem)';
  const dialogMaxHeight = '90vh';

  const streamEventNames = ['progress_event', 'progress'];

  // tasksVersion が変化するたびに状態マシンから最新値を読み取る
  const taskList = $derived.by(() => {
    void tasksVersion;
    return sm.taskList;
  });
  const allFinished = $derived.by(() => {
    void tasksVersion;
    return sm.allFinished;
  });
  const anyRunning = $derived.by(() => {
    void tasksVersion;
    return sm.anyRunning;
  });
  const anyFailure = $derived.by(() => {
    void tasksVersion;
    return sm.anyFailure;
  });
  const phases = $derived.by(() => {
    void tasksVersion;
    return sm.phases;
  });
  const totalItemsProcessed = $derived.by(() => {
    void tasksVersion;
    return sm.totalItemsProcessed;
  });
  const sleepAfterUploadEnabled = $derived(editUploadStatus?.sleepAfterUploadEffective ?? false);
  const sleepToggleDisabled = $derived(optionLoading || optionSaving || !editUploadStatus);

  $effect(() => {
    if (isOpen) {
      ensureStream();
    } else {
      pauseStream();
    }
  });

  $effect(() => {
    if (isOpen !== wasOpen) {
      wasOpen = isOpen;
      if (isOpen) {
        optionErrorMessage = '';
        void loadEditUploadStatus();
      } else {
        optionErrorMessage = '';
        optionLoading = false;
        optionSaving = false;
      }
    }
  });

  onDestroy(() => {
    disposeStream();
    sm.dispose();
  });

  function ensureStream(): void {
    if (eventSource) {
      return;
    }
    openStream();
  }

  function openStream(): void {
    shutdownStream(false);
    connectionState = 'connecting';
    try {
      const source = new EventSource('/api/events/progress');
      messageHandler = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as ProgressEvent;
          if (!payload || typeof payload.task_id !== 'string') {
            return;
          }
          applyEvent(payload);
        } catch (error) {
          console.error('progress-event-parse-failed', error);
        }
      };
      streamEventNames.forEach((name) => {
        source.addEventListener(name, messageHandler as EventListener);
      });
      source.onopen = () => {
        connectionState = 'open';
        reconnectAttempt = 0;
        resetCountdown();
      };
      source.onerror = () => {
        connectionState = 'error';
        shutdownStream(false);
        if (isOpen) {
          scheduleReconnect();
        }
      };
      eventSource = source;
    } catch {
      connectionState = 'error';
      shutdownStream(false);
      if (isOpen) {
        scheduleReconnect();
      }
    }
  }

  function pauseStream(): void {
    shutdownStream(true);
    connectionState = 'idle';
  }

  function disposeStream(): void {
    shutdownStream(true);
  }

  function shutdownStream(resetAttempts: boolean): void {
    if (eventSource) {
      streamEventNames.forEach((name) => {
        if (messageHandler && eventSource) {
          eventSource.removeEventListener(name, messageHandler as EventListener);
        }
      });
      eventSource.onopen = null;
      eventSource.onerror = null;
      eventSource.close();
    }
    eventSource = null;
    messageHandler = null;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    reconnectTimer = null;
    resetCountdown();
    if (resetAttempts) {
      reconnectAttempt = 0;
      retryCountdown = 0;
    }
  }

  function scheduleReconnect(): void {
    if (reconnectTimer || !isOpen) {
      return;
    }
    reconnectAttempt += 1;
    const delay = Math.min(15000, 2000 * reconnectAttempt);
    retryCountdown = Math.ceil(delay / 1000);
    resetCountdown();
    countdownTimer = setInterval(() => {
      if (retryCountdown > 0) {
        retryCountdown -= 1;
      } else {
        resetCountdown();
      }
    }, 1000);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      resetCountdown();
      if (isOpen) {
        openStream();
      }
    }, delay);
  }

  function resetCountdown(): void {
    if (countdownTimer) {
      clearInterval(countdownTimer);
    }
    countdownTimer = null;
    if (!reconnectTimer) {
      retryCountdown = 0;
    }
  }

  async function loadEditUploadStatus(): Promise<void> {
    const requestId = ++statusRequestId;
    optionLoading = true;
    try {
      const status = await fetchEditUploadStatus();
      if (requestId !== statusRequestId) {
        return;
      }
      editUploadStatus = status;
      optionErrorMessage = '';
    } catch (error) {
      if (requestId !== statusRequestId) {
        return;
      }
      optionErrorMessage =
        error instanceof Error ? error.message : '今回の処理オプションの取得に失敗しました。';
    } finally {
      if (requestId === statusRequestId) {
        optionLoading = false;
      }
    }
  }

  async function handleSleepAfterUploadChange(event: Event): Promise<void> {
    if (sleepToggleDisabled) {
      return;
    }

    const target = event.currentTarget as HTMLInputElement;
    const nextValue = target.checked;

    optionSaving = true;
    optionErrorMessage = '';
    try {
      editUploadStatus = await updateEditUploadProcessOptions({
        sleepAfterUpload: nextValue,
      });
    } catch (error) {
      optionErrorMessage =
        error instanceof Error ? error.message : '今回の処理オプションの更新に失敗しました。';
      target.checked = sleepAfterUploadEnabled;
      void loadEditUploadStatus();
    } finally {
      optionSaving = false;
    }
  }

  function applyEvent(event: ProgressEvent): void {
    const isStart = event.kind === 'start';
    sm.applyEvent(event);
    tasksVersion++;
    // start イベント時にオプション状態を再取得する（コンポーネント固有の処理）
    if (
      isStart &&
      isOpen &&
      !optionSaving &&
      !optionLoading &&
      (!editUploadStatus || editUploadStatus.state !== 'running')
    ) {
      void loadEditUploadStatus();
    }
  }

  function manualReconnect(): void {
    if (!isOpen) {
      return;
    }
    shutdownStream(false);
    resetCountdown();
    openStream();
  }

  const closeDisabled = $derived(anyRunning);

  function handleClose(): void {
    if (closeDisabled) {
      return;
    }
    isOpen = false;
  }
</script>

<BaseDialog
  bind:open={isOpen}
  title="進捗"
  showHeader={true}
  showFooter={true}
  footerVariant="custom"
  maxWidth="640px"
  maxHeight={dialogMaxHeight}
  minHeight={dialogMinHeight}
  onClose={handleClose}
>
  <section class="dialog-body">
    <!-- 接続バナー（エラー時のみ表示） -->
    {#if connectionState === 'connecting'}
      <div class="connection-banner connecting" role="status" aria-live="polite">
        <span class="dot dot-1"></span>
        <span class="dot dot-2"></span>
        <span class="dot dot-3"></span>
        接続中…
      </div>
    {:else if connectionState === 'error'}
      <div class="connection-banner error" role="alert">
        接続に失敗しました。
        {#if retryCountdown > 0}
          {retryCountdown}秒後に再試行
        {/if}
        <button type="button" class="retry-button" onclick={manualReconnect}>再接続</button>
      </div>
    {/if}

    <!-- フェーズステッパー -->
    {#if taskList.length > 0}
      <nav class="phase-stepper" aria-label="処理フェーズ">
        {#each phases as phase, i}
          <div class="phase" data-status={phase.status}>
            <span class="phase-dot">
              {#if phase.status === 'completed'}
                <CheckCircle2 size={14} />
              {:else if phase.status === 'failed'}
                <XCircle size={14} />
              {:else if phase.status === 'active'}
                <Loader2 size={14} class="icon-spin" />
              {:else}
                <span class="phase-number">{i + 1}</span>
              {/if}
            </span>
            <span class="phase-label">{phase.label}</span>
          </div>
          {#if i < phases.length - 1}
            <div
              class="phase-connector"
              data-filled={phase.status === 'completed'}
              data-active={phase.status === 'active'}
            ></div>
          {/if}
        {/each}
      </nav>
    {/if}

    <!-- メインコンテンツ -->
    <div class="content-region">
      {#if taskList.length === 0}
        <div class="empty-state">
          <p>
            {#if connectionState === 'open'}
              処理の開始を待っています…
            {:else if connectionState === 'connecting'}
              接続中…
            {:else if connectionState === 'error'}
              接続できませんでした。再接続を待っています…
            {:else}
              進捗データがありません。
            {/if}
          </p>
        </div>
      {:else}
        <!-- 全完了サマリー -->
        {#if allFinished}
          <div
            class="completion-summary"
            class:has-failure={anyFailure}
            role="status"
            aria-live="polite"
          >
            {#if anyFailure}
              <XCircle size={20} />
              <span>一部の処理に失敗しました</span>
            {:else}
              <CheckCircle2 size={20} />
              <span>{totalItemsProcessed}件の動画を処理しました</span>
            {/if}
          </div>
        {:else}
          <!-- 未完了タスクのみ表示 -->
          {#each taskList.filter((t) => t.status !== 'succeeded' && t.status !== 'failed') as task (task.id)}
            <section class="task-section" data-status={task.status}>
              <header class="task-header">
                <span class="task-title">{task.title}</span>
                <span class="task-count">{task.completed}/{task.total}</span>
              </header>
              <div
                class="task-progress"
                role="progressbar"
                aria-label={task.title}
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={sm.taskProgress(task.id)}
              >
                <div class="task-progress-fill" style={`width: ${sm.taskProgress(task.id)}%`}></div>
              </div>

              {#if task.status === 'failed' && task.errorMessage}
                <div class="error-banner" role="alert">
                  <XCircle size={14} />
                  <span>{task.errorMessage}</span>
                </div>
              {/if}

              {#if task.items.length > 0}
                <ul class="item-list">
                  {#each task.items as item, index (item.title + index)}
                    <li class="item-row" data-status={item.status}>
                      <span class="item-icon">
                        {#if item.status === 'active'}
                          <Loader2 size={14} class="icon-spin" />
                        {:else if item.status === 'success'}
                          <CheckCircle2 size={14} />
                        {:else if item.status === 'failure'}
                          <XCircle size={14} />
                        {:else}
                          <Circle size={14} />
                        {/if}
                      </span>
                      <span class="item-name">{item.title}</span>
                    </li>
                    {#if item.status === 'active' && item.steps.length > 1}
                      <li class="item-steps-row">
                        <ol class="step-indicators">
                          {#each item.steps as step (step.key)}
                            <li
                              class="step-dot"
                              data-status={step.status}
                              title={step.label}
                              aria-label="{step.label}: {step.status === 'active'
                                ? '実行中'
                                : step.status === 'success'
                                  ? '完了'
                                  : step.status === 'failure'
                                    ? '失敗'
                                    : '待機中'}"
                            >
                              {#if step.status === 'active'}
                                <Loader2 size={10} class="icon-spin" />
                              {:else if step.status === 'success'}
                                <CheckCircle2 size={10} />
                              {:else if step.status === 'failure'}
                                <XCircle size={10} />
                              {:else}
                                <Circle size={10} />
                              {/if}
                              <span class="step-dot-label">{step.label}</span>
                            </li>
                          {/each}
                        </ol>
                      </li>
                    {/if}
                  {/each}
                </ul>
              {/if}
            </section>
          {/each}
        {/if}
      {/if}
    </div>
  </section>

  {#snippet footer()}
    <footer class="dialog-footer">
      <!-- スリープトグル -->
      <div class="footer-option">
        <label class="sleep-toggle" class:disabled={sleepToggleDisabled}>
          <input
            type="checkbox"
            checked={sleepAfterUploadEnabled}
            disabled={sleepToggleDisabled}
            aria-label="完了後スリープ"
            onchange={handleSleepAfterUploadChange}
          />
          <span class="toggle-slider"></span>
          <span class="toggle-label">完了後スリープ</span>
        </label>
        {#if optionErrorMessage}
          <span class="option-error" role="alert">{optionErrorMessage}</span>
        {/if}
      </div>

      <div class="footer-actions">
        <button
          type="button"
          class="action-button primary"
          onclick={handleClose}
          disabled={closeDisabled}
          title={closeDisabled ? '処理中は閉じることができません' : ''}
        >
          閉じる
        </button>
      </div>
    </footer>
  {/snippet}
</BaseDialog>

<style>
  /* ====== レイアウト ====== */
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 0.75rem 1.25rem;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  .content-region {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    scrollbar-gutter: stable;
  }

  /* ====== 接続バナー ====== */
  .connection-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
    font-size: 0.82rem;
    flex-shrink: 0;
  }

  .connection-banner.connecting {
    color: rgba(var(--theme-rgb-accent), 0.85);
    background: rgba(var(--theme-rgb-accent), 0.08);
  }

  .connection-banner.error {
    color: rgba(var(--theme-rgb-danger-pale), 0.95);
    background: rgba(var(--theme-rgb-danger-bright), 0.1);
    border: 1px solid rgba(var(--theme-rgb-danger-soft), 0.2);
  }

  .retry-button {
    margin-left: auto;
    padding: 0.3rem 0.7rem;
    border-radius: 0.4rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.15);
    color: rgba(var(--theme-rgb-white), 0.8);
    background: transparent;
    cursor: pointer;
    font-size: 0.8rem;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .retry-button:hover {
    border-color: rgba(var(--theme-rgb-white), 0.35);
    color: var(--theme-color-white);
  }

  .dot {
    width: 0.35rem;
    height: 0.35rem;
    border-radius: 50%;
    background: rgba(var(--theme-rgb-accent), 0.4);
    opacity: 0.75;
  }

  /* ====== フェーズステッパー ====== */
  .phase-stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    padding: 0.5rem 1rem;
    flex-shrink: 0;
  }

  .phase {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .phase-dot {
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 700;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .phase-number {
    font-size: 0.7rem;
    font-weight: 700;
  }

  .phase[data-status='pending'] .phase-dot {
    background: rgba(var(--theme-rgb-white), 0.06);
    color: rgba(var(--theme-rgb-white), 0.35);
    border: 1.5px solid rgba(var(--theme-rgb-white), 0.1);
  }

  .phase[data-status='active'] .phase-dot {
    background: rgba(var(--theme-rgb-accent), 0.18);
    color: rgba(var(--theme-rgb-accent), 0.95);
    border: 1.5px solid rgba(var(--theme-rgb-accent), 0.45);
    box-shadow: 0 0 0.35rem rgba(var(--theme-rgb-accent), 0.18);
  }

  .phase[data-status='completed'] .phase-dot {
    background: rgba(var(--theme-rgb-success), 0.2);
    color: rgba(var(--theme-rgb-success), 0.9);
    border: 1.5px solid rgba(var(--theme-rgb-success), 0.4);
  }

  .phase[data-status='failed'] .phase-dot {
    background: rgba(var(--theme-rgb-danger), 0.18);
    color: rgba(var(--theme-rgb-danger), 0.9);
    border: 1.5px solid rgba(var(--theme-rgb-danger), 0.4);
  }

  .phase-label {
    font-size: 0.78rem;
    font-weight: 500;
    color: rgba(var(--theme-rgb-white), 0.45);
    transition: color 0.2s ease;
  }

  .phase[data-status='active'] .phase-label {
    color: rgba(var(--theme-rgb-accent), 0.9);
  }

  .phase[data-status='completed'] .phase-label {
    color: rgba(var(--theme-rgb-success), 0.8);
  }

  .phase[data-status='failed'] .phase-label {
    color: rgba(var(--theme-rgb-danger), 0.8);
  }

  .phase-connector {
    flex: 1;
    height: 1.5px;
    margin: 0 0.6rem;
    background: rgba(var(--theme-rgb-white), 0.08);
    border-radius: 1px;
    transition: background 0.3s ease;
  }

  .phase-connector[data-filled='true'] {
    background: rgba(var(--theme-rgb-success), 0.4);
  }

  .phase-connector[data-active='true'] {
    background: linear-gradient(
      90deg,
      rgba(var(--theme-rgb-accent), 0.45),
      rgba(var(--theme-rgb-white), 0.08)
    );
  }

  /* ====== 空状態 ====== */
  .empty-state {
    display: grid;
    place-items: center;
    padding: 3rem 1rem;
    border: 1px dashed rgba(var(--theme-rgb-white), 0.08);
    border-radius: 0.75rem;
    color: rgba(var(--theme-rgb-white), 0.5);
    text-align: center;
  }

  /* ====== 完了サマリー ====== */
  .completion-summary {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.65rem 0.85rem;
    border-radius: 0.6rem;
    background: rgba(var(--theme-rgb-success), 0.06);
    border: 1px solid rgba(var(--theme-rgb-success), 0.15);
    color: rgba(var(--theme-rgb-success), 0.85);
    font-size: 0.85rem;
    font-weight: 500;
    flex-shrink: 0;
  }

  .completion-summary.has-failure {
    background: rgba(var(--theme-rgb-danger-bright), 0.08);
    border-color: rgba(var(--theme-rgb-danger-soft), 0.2);
    color: rgba(var(--theme-rgb-danger-pale), 0.9);
  }

  /* ====== タスクセクション ====== */
  .task-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    background: rgba(var(--theme-rgb-white), 0.03);
    border: 1px solid rgba(var(--theme-rgb-white), 0.06);
  }

  .task-section[data-status='running'] {
    border-color: rgba(var(--theme-rgb-accent), 0.1);
    background: linear-gradient(
      160deg,
      rgba(var(--theme-rgb-accent), 0.03) 0%,
      rgba(var(--theme-rgb-white), 0.02) 100%
    );
  }

  .task-section[data-status='failed'] {
    border-color: rgba(var(--theme-rgb-danger-soft), 0.2);
  }

  .task-header {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .task-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: rgba(var(--theme-rgb-white), 0.88);
  }

  .task-count {
    font-size: 0.75rem;
    color: rgba(var(--theme-rgb-white), 0.4);
    font-variant-numeric: tabular-nums;
    margin-left: auto;
    flex-shrink: 0;
  }

  .task-section[data-status='failed'] .task-header :global(svg) {
    color: rgba(var(--theme-rgb-danger-soft), 0.7);
  }

  .task-progress {
    height: 0.3rem;
    border-radius: 0.3rem;
    background: rgba(var(--theme-rgb-white), 0.06);
    overflow: hidden;
  }

  .task-progress-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--accent-color), var(--theme-accent-color-alt));
    transition: width 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
  }

  .task-section[data-status='running'] .task-progress-fill {
    background: linear-gradient(
      90deg,
      var(--accent-color),
      var(--theme-accent-color-alt),
      var(--accent-color)
    );
    background-size: 200% 100%;
    background-position: 50% 0;
  }

  .task-section[data-status='succeeded'] .task-progress-fill {
    background: rgba(var(--theme-rgb-success), 0.5);
  }

  /* ====== エラーバナー ====== */
  .error-banner {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.6rem;
    border-radius: 0.4rem;
    font-size: 0.8rem;
    background: rgba(var(--theme-rgb-danger-bright), 0.1);
    color: rgba(var(--theme-rgb-danger-pale), 0.9);
    border: 1px solid rgba(var(--theme-rgb-danger-soft), 0.2);
  }

  /* ====== アイテムリスト ====== */
  .item-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .item-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.4rem;
    border-radius: 0.35rem;
  }

  .item-row[data-status='active'] {
    background: rgba(var(--theme-rgb-accent), 0.05);
  }

  .item-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    color: rgba(var(--theme-rgb-white), 0.18);
  }

  .item-row[data-status='active'] .item-icon {
    color: rgba(var(--theme-rgb-accent), 0.9);
  }

  .item-row[data-status='success'] .item-icon {
    color: rgba(var(--theme-rgb-accent), 0.55);
  }

  .item-row[data-status='failure'] .item-icon {
    color: rgba(var(--theme-rgb-danger-soft), 0.8);
  }

  .item-name {
    flex: 1;
    font-size: 0.82rem;
    color: rgba(var(--theme-rgb-white), 0.8);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-row[data-status='success'] .item-name {
    color: rgba(var(--theme-rgb-white), 0.38);
  }

  /* ====== ステップインジケーター ====== */
  .item-steps-row {
    padding: 0.15rem 0.4rem 0.35rem 1.75rem;
  }

  .step-indicators {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.1rem 0.5rem;
  }

  .step-dot {
    display: flex;
    align-items: center;
    gap: 0.2rem;
    color: rgba(var(--theme-rgb-white), 0.18);
  }

  .step-dot[data-status='active'] {
    color: rgba(var(--theme-rgb-accent), 0.9);
  }

  .step-dot[data-status='success'] {
    color: rgba(var(--theme-rgb-accent), 0.5);
  }

  .step-dot[data-status='failure'] {
    color: rgba(var(--theme-rgb-danger-soft), 0.8);
  }

  .step-dot-label {
    font-size: 0.7rem;
    line-height: 1;
  }

  @keyframes progress-icon-spin {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  :global(.icon-spin) {
    animation: progress-icon-spin 1s linear infinite;
  }

  /* ====== フッター ====== */
  .dialog-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 1.25rem;
  }

  .footer-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .sleep-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    flex-shrink: 0;
  }

  .sleep-toggle.disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .sleep-toggle input[type='checkbox'] {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .sleep-toggle .toggle-slider {
    position: relative;
    display: inline-block;
    width: 2.4rem;
    height: 1.3rem;
    background: rgba(var(--theme-rgb-white), 0.12);
    border: 1px solid rgba(var(--theme-rgb-white), 0.15);
    border-radius: 1rem;
    transition: all 0.25s ease;
    flex-shrink: 0;
  }

  .sleep-toggle .toggle-slider::before {
    content: '';
    position: absolute;
    width: 0.9rem;
    height: 0.9rem;
    left: 0.2rem;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(var(--theme-rgb-white), 0.85);
    border-radius: 50%;
    transition: all 0.25s ease;
  }

  .sleep-toggle input:checked + .toggle-slider {
    background: rgba(var(--theme-rgb-accent), 0.7);
    border-color: rgba(var(--theme-rgb-accent), 0.5);
  }

  .sleep-toggle input:checked + .toggle-slider::before {
    left: calc(100% - 1.1rem);
    background: rgba(var(--theme-rgb-white), 0.95);
  }

  .sleep-toggle input:focus-visible + .toggle-slider {
    outline: 2px solid rgba(var(--theme-rgb-accent), 0.5);
    outline-offset: 2px;
  }

  .toggle-label {
    font-size: 0.78rem;
    color: rgba(var(--theme-rgb-white), 0.55);
    white-space: nowrap;
  }

  .option-error {
    font-size: 0.75rem;
    color: var(--theme-status-danger-soft);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .footer-actions {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-shrink: 0;
  }

  .action-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.55rem 1.2rem;
    border-radius: 0.5rem;
    font-size: 0.82rem;
    font-weight: 600;
    border: 1px solid rgba(var(--theme-rgb-accent), 0.3);
    color: rgba(var(--theme-rgb-accent), 0.9);
    background: rgba(var(--theme-rgb-accent), 0.08);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .action-button:hover:not(:disabled) {
    border-color: rgba(var(--theme-rgb-accent), 0.55);
    color: var(--theme-accent-ink);
    background: linear-gradient(135deg, var(--accent-color), var(--theme-accent-color-alt));
    box-shadow: 0 0.25rem 0.75rem rgba(var(--theme-rgb-accent), 0.3);
  }

  .action-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* ====== レスポンシブ ====== */
  @media (max-width: 480px) {
    .dialog-body {
      padding: 0.5rem 0.75rem;
    }

    .dialog-footer {
      flex-direction: column;
      gap: 0.5rem;
    }

    .footer-option {
      width: 100%;
    }

    .footer-actions {
      width: 100%;
      justify-content: flex-end;
    }

    .phase-stepper {
      padding: 0.25rem 0.5rem;
    }

    .phase-dot {
      width: 1.25rem;
      height: 1.25rem;
    }

    .phase-label {
      font-size: 0.7rem;
    }
  }
</style>
