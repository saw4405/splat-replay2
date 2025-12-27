<script lang="ts">
  import { onDestroy } from 'svelte';
  import BaseDialog from '../../common/components/BaseDialog.svelte';
  import type { ProgressEvent } from './../api';

  type ConnectionState = 'idle' | 'connecting' | 'open' | 'error';
  type TaskStatus = 'idle' | 'running' | 'succeeded' | 'failed';
  type ItemStatus = 'pending' | 'active' | 'success' | 'failure';
  type StepStatus = ItemStatus;

  interface StepState {
    key: string;
    label: string;
    status: StepStatus;
    message: string | null;
  }

  interface ItemState {
    title: string;
    status: ItemStatus;
    steps: StepState[];
    activeStepKey: string | null;
    expanded: boolean;
  }

  interface TaskState {
    id: string;
    title: string;
    total: number;
    completed: number;
    status: TaskStatus;
    items: ItemState[];
    activeIndex: number | null;
    errorMessage: string | null;
    successMessage: string | null;
    lastUpdated: number;
  }

  export let isOpen = false;

  let tasks: Record<string, TaskState> = {};

  let eventSource: EventSource | null = null;
  let messageHandler: ((event: MessageEvent) => void) | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let countdownTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectAttempt = 0;
  let retryCountdown = 0;

  let connectionState: ConnectionState = 'idle';

  const dialogMinHeight = 'min(70vh, 46rem)';
  const dialogMaxHeight = '90vh';

  const taskOrder = ['auto_edit', 'auto_upload'];

  const taskLabels: Record<string, string> = {
    auto_edit: '自動編集',
    auto_upload: '自動アップロード',
  };

  const defaultTaskSteps: Record<string, Array<{ key: string; label: string }>> = {
    auto_edit: [
      { key: 'edit_group', label: 'グループ編集' },
      { key: 'concat', label: '動画結合' },
      { key: 'subtitle', label: '字幕編集' },
      { key: 'metadata', label: 'メタデータ編集' },
      { key: 'thumbnail', label: 'サムネイル編集' },
      { key: 'volume', label: '音量調整' },
      { key: 'save', label: '保存' },
    ],
    auto_upload: [
      { key: 'collect', label: '編集済み動画収集' },
      { key: 'upload', label: '動画アップロード' },
      { key: 'caption', label: '字幕アップロード' },
      { key: 'thumb', label: 'サムネイルアップロード' },
      { key: 'playlist', label: 'プレイリスト追加' },
      { key: 'delete', label: '編集済み動画削除' },
    ],
  };
  const stageKeyMappings: Record<string, Record<string, { key: string; label: string }>> = {
    auto_edit: {
      edit_group: { key: 'edit_group', label: 'グループ編集' },
      concat: { key: 'concat', label: '動画結合' },
      subtitle: { key: 'subtitle', label: '字幕編集' },
      metadata: { key: 'metadata', label: 'メタデータ編集' },
      thumbnail: { key: 'thumbnail', label: 'サムネイル編集' },
      volume: { key: 'volume', label: '音量調整' },
      save: { key: 'save', label: '保存' },
    },
    auto_upload: {
      prepare: { key: 'collect', label: '編集済み動画収集' },
      collect: { key: 'collect', label: '編集済み動画収集' },
      upload: { key: 'upload', label: '動画アップロード' },
      caption: { key: 'caption', label: '字幕アップロード' },
      thumb: { key: 'thumb', label: 'サムネイルアップロード' },
      playlist: { key: 'playlist', label: 'プレイリスト追加' },
      delete: { key: 'delete', label: '編集済み動画削除' },
    },
  };

  const streamEventNames = ['progress_event', 'progress'];

  $: orderedTasks = taskOrder
    .map((id) => tasks[id])
    .filter((task): task is TaskState => Boolean(task));

  $: extraTasks = Object.values(tasks).filter((task) => !taskOrder.includes(task.id));

  $: taskList = [...orderedTasks, ...extraTasks];

  $: allFinished =
    taskList.length > 0 &&
    taskList.every((task) => task.status === 'succeeded' || task.status === 'failed');

  $: anyRunning = taskList.some((task) => task.status === 'running');
  $: anyFailure = taskList.some((task) => task.status === 'failed');

  $: if (isOpen) {
    ensureStream();
  } else {
    pauseStream();
  }

  onDestroy(() => {
    disposeStream();
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

  function applyEvent(event: ProgressEvent): void {
    switch (event.kind) {
      case 'start':
        handleStart(event);
        break;
      case 'items':
        handleItems(event);
        break;
      case 'item_stage':
        handleItemStage(event);
        break;
      case 'item_finish':
        handleItemFinish(event);
        break;
      case 'stage':
        handleStage(event);
        break;
      case 'total':
        handleTotal(event);
        break;
      case 'advance':
        handleAdvance(event);
        break;
      case 'finish':
        handleFinish(event);
        break;
      default:
        break;
    }
  }
  function handleStart(event: ProgressEvent): void {
    const taskId = event.task_id;
    const title = formatTaskTitle(taskId, event.task_name);
    const items = Array.isArray(event.items) ? event.items : [];
    const createdItems = items.map((itemTitle, index) => makeItem(taskId, itemTitle, index === 0));
    const total =
      typeof event.total === 'number' && Number.isFinite(event.total)
        ? Math.max(0, event.total)
        : createdItems.length;
    const completed =
      typeof event.completed === 'number' && Number.isFinite(event.completed)
        ? Math.max(0, event.completed)
        : 0;
    const task: TaskState = {
      id: taskId,
      title,
      total,
      completed,
      status: 'running',
      items: createdItems,
      activeIndex: createdItems.length > 0 ? 0 : null,
      errorMessage: null,
      successMessage: event.message ?? null,
      lastUpdated: Date.now(),
    };
    tasks = { ...tasks, [taskId]: task };
  }

  function handleItems(event: ProgressEvent): void {
    const taskId = event.task_id;
    if (!Array.isArray(event.items)) {
      return;
    }
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      event.items!.forEach((title, index) => {
        if (draft.items[index]) {
          if (!draft.items[index].title || draft.items[index].title.startsWith('アイテム')) {
            draft.items[index].title = title;
          }
        } else {
          draft.items.push(makeItem(taskId, title, false));
        }
      });
      if (draft.total === 0) {
        draft.total = event.items!.length;
      }
    });
  }

  function handleItemStage(event: ProgressEvent): void {
    const taskId = event.task_id;
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      const index =
        typeof event.item_index === 'number' && event.item_index >= 0
          ? event.item_index
          : (draft.activeIndex ?? draft.items.length);
      if (index < 0) {
        return;
      }
      ensureItemExists(draft, index, event.message ?? event.item_label ?? null);
      setActiveItem(draft, index);
      const item = draft.items[index];
      const mapped = mapStageKey(taskId, event.item_key ?? '');
      const stepKey = mapped?.key ?? event.item_key ?? `step_${item.steps.length}`;
      const stepLabel = mapped?.label ?? event.item_label ?? defaultStepLabel(stepKey);
      setActiveStep(item, stepKey, stepLabel, event.message ?? null);
      draft.status = 'running';
    });
  }

  function handleItemFinish(event: ProgressEvent): void {
    const taskId = event.task_id;
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      const index =
        typeof event.item_index === 'number' && event.item_index >= 0
          ? event.item_index
          : (draft.activeIndex ?? -1);
      if (index < 0 || !draft.items[index]) {
        return;
      }
      const item = draft.items[index];
      const success = event.success !== false;
      if (success) {
        markItemSuccess(item);
      } else {
        markItemFailure(item, event.message ?? null);
      }
      draft.activeIndex = success ? pickNextIndex(draft, index) : index;
    });
  }

  function handleStage(event: ProgressEvent): void {
    const taskId = event.task_id;
    const stageKey = event.stage_key ?? '';
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      if (taskId === 'auto_edit' && stageKey === 'edit_group') {
        const title = pickStageTitle(event);
        const index = findItemIndexByTitle(draft, title);
        const targetIndex =
          index >= 0 ? index : draft.items.push(makeItem(taskId, title, false)) - 1;
        setActiveItem(draft, targetIndex);
        draft.items[targetIndex].title = title;
        return;
      }
      if (taskId === 'auto_upload' && stageKey === 'prepare') {
        const title = pickStageTitle(event);
        const index = findItemIndexByTitle(draft, title);
        const targetIndex =
          index >= 0 ? index : draft.items.push(makeItem(taskId, title, false)) - 1;
        setActiveItem(draft, targetIndex);
        draft.items[targetIndex].title = title;
        const mapped = mapStageKey(taskId, 'collect');
        setActiveStep(
          draft.items[targetIndex],
          mapped?.key ?? 'collect',
          mapped?.label ?? '編集済み動画収集',
          event.message ?? null
        );
        return;
      }
      if (draft.activeIndex === null) {
        return;
      }
      const current = draft.items[draft.activeIndex];
      if (!current) {
        return;
      }
      const mapped = mapStageKey(taskId, stageKey);
      const stepKey = mapped?.key ?? stageKey;
      const stepLabel = mapped?.label ?? event.stage_label ?? defaultStepLabel(stepKey);
      setActiveStep(current, stepKey, stepLabel, event.message ?? null);
    });
  }

  function handleTotal(event: ProgressEvent): void {
    const taskId = event.task_id;
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      if (typeof event.total === 'number' && Number.isFinite(event.total)) {
        draft.total = Math.max(0, event.total);
      }
    });
  }

  function handleAdvance(event: ProgressEvent): void {
    const taskId = event.task_id;
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      if (typeof event.completed === 'number' && Number.isFinite(event.completed)) {
        draft.completed = Math.max(0, event.completed);
      } else if (draft.total > 0) {
        draft.completed = Math.min(draft.total, draft.completed + 1);
      }
      if (draft.activeIndex !== null && draft.items[draft.activeIndex]) {
        markItemSuccess(draft.items[draft.activeIndex]);
        draft.activeIndex = pickNextIndex(draft, draft.activeIndex);
      }
    });
  }

  function handleFinish(event: ProgressEvent): void {
    const taskId = event.task_id;
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      const success = event.success !== false;
      draft.status = success ? 'succeeded' : 'failed';
      draft.completed =
        typeof event.completed === 'number' && Number.isFinite(event.completed)
          ? Math.max(0, event.completed)
          : draft.total;
      if (success) {
        draft.successMessage = event.message ?? 'すべての処理が完了しました。';
        draft.errorMessage = null;
        draft.items.forEach((item) => {
          if (item.status !== 'success') {
            markItemSuccess(item);
          }
        });
        draft.activeIndex = null;
      } else {
        draft.errorMessage = event.message ?? '処理に失敗しました。';
        if (draft.activeIndex !== null && draft.items[draft.activeIndex]) {
          markItemFailure(draft.items[draft.activeIndex], event.message ?? null);
        }
        draft.successMessage = null;
      }
    });
  }
  function markItemSuccess(item: ItemState): void {
    item.status = 'success';
    item.expanded = false;
    if (item.activeStepKey) {
      const step = item.steps.find((s) => s.key === item.activeStepKey);
      if (step) {
        step.status = 'success';
      }
    }
    item.steps.forEach((step) => {
      if (step.status === 'active') {
        step.status = 'success';
      }
    });
    item.activeStepKey = null;
  }

  function markItemFailure(item: ItemState, message: string | null): void {
    item.status = 'failure';
    item.expanded = true;
    if (item.activeStepKey) {
      const step = item.steps.find((s) => s.key === item.activeStepKey);
      if (step) {
        step.status = 'failure';
        step.message = message;
      }
    }
    item.steps.forEach((step) => {
      if (step.status === 'active') {
        step.status = 'failure';
        if (message && !step.message) {
          step.message = message;
        }
      }
    });
    item.activeStepKey = null;
  }

  function setActiveItem(task: TaskState, index: number): void {
    if (index < 0 || index >= task.items.length) {
      return;
    }
    if (task.activeIndex !== null && task.activeIndex !== index) {
      const previous = task.items[task.activeIndex];
      if (previous && previous.status === 'active') {
        previous.status = 'pending';
      }
    }
    task.activeIndex = index;
    const current = task.items[index];
    current.status = 'active';
    current.expanded = true;
  }

  function setActiveStep(
    item: ItemState,
    key: string,
    label: string,
    message: string | null
  ): void {
    if (item.activeStepKey && item.activeStepKey !== key) {
      const previous = item.steps.find((step) => step.key === item.activeStepKey);
      if (previous && previous.status === 'active') {
        previous.status = 'success';
      }
    }
    let step = item.steps.find((s) => s.key === key);
    if (!step) {
      step = { key, label, status: 'pending', message: null };
      item.steps.push(step);
    }
    step.label = label;
    step.message = message;
    step.status = 'active';
    item.activeStepKey = key;
    if (item.status !== 'success' && item.status !== 'failure') {
      item.status = 'active';
    }
  }

  function ensureItemExists(task: TaskState, index: number, titleHint: string | null): void {
    while (task.items.length <= index) {
      task.items.push(makeItem(task.id, defaultItemTitle(task.id, task.items.length), false));
    }
    const item = task.items[index];
    if (titleHint && titleHint.trim().length > 0) {
      item.title = titleHint.trim();
    }
  }

  function pickNextIndex(task: TaskState, currentIndex: number): number | null {
    const nextIndex = currentIndex + 1;
    return nextIndex < task.items.length ? nextIndex : null;
  }

  function defaultItemTitle(taskId: string, index: number): string {
    const base = taskLabels[taskId] ?? 'アイテム';
    return `${base} ${index + 1}`;
  }

  function defaultTaskTitle(taskId: string): string {
    return taskLabels[taskId] ?? taskId;
  }

  function formatTaskTitle(taskId: string, provided?: string | null): string {
    if (provided && provided.trim().length > 0) {
      return provided.trim();
    }
    return defaultTaskTitle(taskId);
  }

  function createDefaultSteps(taskId: string): StepState[] {
    const defs = defaultTaskSteps[taskId];
    if (!defs) {
      return [];
    }
    return defs.map((def) => ({
      key: def.key,
      label: def.label,
      status: 'pending',
      message: null,
    }));
  }

  function makeItem(taskId: string, title: string, active: boolean): ItemState {
    return {
      title: title || defaultItemTitle(taskId, 0),
      status: active ? 'active' : 'pending',
      steps: createDefaultSteps(taskId),
      activeStepKey: null,
      expanded: active,
    };
  }

  function mapStageKey(taskId: string, key: string): { key: string; label: string } | null {
    if (!key) {
      return null;
    }
    const mapping = stageKeyMappings[taskId];
    if (!mapping) {
      return null;
    }
    return mapping[key] ?? null;
  }

  function defaultStepLabel(key: string): string {
    if (!key) {
      return '処理';
    }
    return key.replace(/_/g, ' ');
  }

  function pickStageTitle(event: ProgressEvent): string {
    return (
      (event.stage_label && event.stage_label.trim()) ||
      (event.message && String(event.message).trim()) ||
      defaultItemTitle(event.task_id, 0)
    );
  }

  function findItemIndexByTitle(task: TaskState, title: string): number {
    if (!title) {
      return -1;
    }
    return task.items.findIndex((item) => item.title === title);
  }

  function cloneTask(task: TaskState): TaskState {
    return {
      ...task,
      items: task.items.map((item) => ({
        ...item,
        steps: item.steps.map((step) => ({ ...step })),
      })),
    };
  }

  function updateTask(
    taskId: string,
    fallbackTitle: string | undefined,
    mutator: (draft: TaskState) => void
  ): TaskState {
    const current = tasks[taskId] ?? {
      id: taskId,
      title: formatTaskTitle(taskId, fallbackTitle),
      total: 0,
      completed: 0,
      status: 'idle',
      items: [],
      activeIndex: null,
      errorMessage: null,
      successMessage: null,
      lastUpdated: Date.now(),
    };
    const draft = cloneTask(current);
    if ((!draft.title || draft.title === current.title) && fallbackTitle) {
      draft.title = formatTaskTitle(taskId, fallbackTitle);
    }
    mutator(draft);
    draft.lastUpdated = Date.now();
    tasks = { ...tasks, [taskId]: draft };
    return draft;
  }

  function taskProgress(task: TaskState): number {
    if (task.total <= 0) {
      return 0;
    }
    const ratio = Math.max(0, Math.min(1, task.completed / task.total));
    return Math.round(ratio * 100);
  }

  function itemStatusLabel(status: ItemStatus): string {
    switch (status) {
      case 'active':
        return '進行中';
      case 'success':
        return '完了';
      case 'failure':
        return '失敗';
      default:
        return '待機中';
    }
  }

  function stepStatusLabel(status: StepStatus): string {
    switch (status) {
      case 'active':
        return '進行中';
      case 'success':
        return '完了';
      case 'failure':
        return '失敗';
      default:
        return '待機中';
    }
  }

  function toggleItem(taskId: string, index: number): void {
    updateTask(taskId, undefined, (draft) => {
      if (!draft.items[index]) {
        return;
      }
      draft.items[index].expanded = !draft.items[index].expanded;
    });
  }

  function manualReconnect(): void {
    if (!isOpen) {
      return;
    }
    shutdownStream(false);
    resetCountdown();
    openStream();
  }

  function handleClose(): void {
    isOpen = false;
  }
</script>

<BaseDialog
  bind:open={isOpen}
  title="進捗ダイアログ"
  showHeader={true}
  showFooter={true}
  footerVariant="custom"
  maxWidth="960px"
  maxHeight={dialogMaxHeight}
  minHeight={dialogMinHeight}
  on:close={handleClose}
>
  <section class="dialog-body">
    {#if connectionState === 'connecting'}
      <div class="connection-banner connecting" role="status" aria-live="polite">
        <span class="dot dot-1"></span>
        <span class="dot dot-2"></span>
        <span class="dot dot-3"></span>
        サーバーと接続中です…
      </div>
    {:else if connectionState === 'error'}
      <div class="connection-banner error" role="alert">
        進捗ストリームへの接続に失敗しました。
        {#if retryCountdown > 0}
          {retryCountdown} 秒後に再接続を試行します。
        {/if}
        <button type="button" class="retry-button" on:click={manualReconnect}> 再接続 </button>
      </div>
    {/if}

    <div class="content-region">
      {#if taskList.length === 0}
        <div class="empty-state">
          <p>まだ進捗データがありません。</p>
          {#if connectionState === 'open'}
            <p class="hint">自動編集または自動アップロードを開始すると表示されます。</p>
          {/if}
        </div>
      {:else}
        <div class="tasks-grid">
          {#each taskList as task (task.id)}
            <article class="task-card" data-status={task.status}>
              <header class="task-header">
                <div class="task-title-group">
                  <h3>{task.title}</h3>
                  <span class="task-subtitle">{task.completed}/{task.total}</span>
                </div>
                <div
                  class="task-progress"
                  role="progressbar"
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-valuenow={taskProgress(task)}
                >
                  <div class="task-progress-fill" style={`width: ${taskProgress(task)}%`} />
                  <span class="task-progress-label">{taskProgress(task)}%</span>
                </div>
              </header>

              {#if task.status === 'failed' && task.errorMessage}
                <div class="status-banner error" role="alert">
                  {task.errorMessage}
                </div>
              {:else if task.status === 'succeeded' && task.successMessage}
                <div class="status-banner success" role="status">
                  {task.successMessage}
                </div>
              {/if}

              <div class="task-body">
                {#if task.items.length === 0}
                  <div class="empty-items">処理対象が見つかりませんでした。</div>
                {:else}
                  {#each task.items as item, index (item.title + index)}
                    <section class="item" data-status={item.status}>
                      <button
                        type="button"
                        class="item-header"
                        aria-expanded={item.expanded}
                        on:click={() => toggleItem(task.id, index)}
                      >
                        <span class="item-index">{index + 1}</span>
                        <span class="item-title">{item.title}</span>
                        <span class="item-chip" data-status={item.status}>
                          {itemStatusLabel(item.status)}
                        </span>
                      </button>
                      {#if item.expanded}
                        <ul class="step-list">
                          {#if item.steps.length === 0}
                            <li class="step pending">
                              <span class="step-marker"></span>
                              <span class="step-label">進捗待機中</span>
                            </li>
                          {:else}
                            {#each item.steps as step (step.key)}
                              <li class={`step ${step.status}`}>
                                <span class="step-marker"></span>
                                <div class="step-content">
                                  <span class="step-label">{step.label}</span>
                                  <span class="step-chip" data-status={step.status}>
                                    {stepStatusLabel(step.status)}
                                  </span>
                                  {#if step.message}
                                    <span class="step-message">{step.message}</span>
                                  {/if}
                                </div>
                              </li>
                            {/each}
                          {/if}
                        </ul>
                      {/if}
                    </section>
                  {/each}
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </div>
  </section>

  <footer slot="footer" class="dialog-footer">
    <div class="footer-status">
      {#if anyRunning}
        <span class="footer-indicator running">処理中</span>
      {:else if anyFailure}
        <span class="footer-indicator failed">失敗あり</span>
      {:else if allFinished}
        <span class="footer-indicator done">完了</span>
      {/if}
    </div>
    <button
      type="button"
      class="action-button primary"
      on:click={handleClose}
      disabled={!allFinished && anyRunning}
    >
      閉じる
    </button>
  </footer>
</BaseDialog>

<style>
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem 1.5rem;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  .content-region {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    padding-right: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    scrollbar-gutter: stable both-edges;
  }

  .connection-banner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    font-size: 0.9rem;
    flex-shrink: 0;
  }

  .connection-banner.connecting {
    color: rgba(25, 211, 199, 0.9);
    background: rgba(25, 211, 199, 0.1);
  }

  .connection-banner.error {
    color: rgba(255, 122, 122, 0.95);
    background: rgba(255, 77, 109, 0.14);
    border: 1px solid rgba(255, 99, 132, 0.25);
  }

  .retry-button {
    margin-left: auto;
    padding: 0.4rem 0.9rem;
    border-radius: 0.6rem;
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: rgba(255, 255, 255, 0.85);
    background: transparent;
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }

  .retry-button:hover {
    border-color: rgba(255, 255, 255, 0.4);
    color: #ffffff;
  }

  .dot {
    width: 0.4rem;
    height: 0.4rem;
    border-radius: 50%;
    background: rgba(25, 211, 199, 0.4);
    animation: pulse 1.4s infinite ease-in-out;
  }

  .dot-2 {
    animation-delay: 0.2s;
  }

  .dot-3 {
    animation-delay: 0.4s;
  }

  @keyframes pulse {
    0%,
    80%,
    100% {
      opacity: 0.3;
      transform: scale(0.9);
    }
    40% {
      opacity: 1;
      transform: scale(1);
    }
  }

  .empty-state {
    display: grid;
    place-items: center;
    padding: 3rem 1rem;
    border: 1px dashed rgba(255, 255, 255, 0.1);
    border-radius: 1rem;
    color: rgba(255, 255, 255, 0.6);
    text-align: center;
    gap: 0.5rem;
  }

  .empty-state .hint {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.45);
  }

  .tasks-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.25rem;
  }

  .task-card {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.25rem;
    border-radius: 1rem;
    background: linear-gradient(155deg, rgba(18, 26, 33, 0.9), rgba(10, 14, 18, 0.96));
    border: 1px solid rgba(25, 211, 199, 0.08);
    box-shadow: 0 0.75rem 2.25rem rgba(0, 0, 0, 0.35);
  }

  .task-card[data-status='succeeded'] {
    border-color: rgba(25, 211, 199, 0.35);
  }

  .task-card[data-status='failed'] {
    border-color: rgba(255, 99, 132, 0.28);
    box-shadow: 0 0.75rem 2.5rem rgba(255, 99, 132, 0.15);
  }

  .task-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .task-title-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .task-title-group h3 {
    margin: 0;
    font-size: 1.05rem;
    color: rgba(255, 255, 255, 0.92);
    font-weight: 600;
  }

  .task-subtitle {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.45);
  }

  .task-progress {
    position: relative;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    width: 8rem;
    height: 0.75rem;
    border-radius: 0.75rem;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
  }

  .task-progress-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #19d3c7, #1dd1a1);
    transition: width 0.3s ease;
  }

  .task-progress-label {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.92);
    font-weight: 600;
    text-shadow: 0 0 6px rgba(0, 0, 0, 0.45);
  }

  .status-banner {
    padding: 0.6rem 0.85rem;
    border-radius: 0.8rem;
    font-size: 0.85rem;
  }

  .status-banner.success {
    background: rgba(25, 211, 199, 0.1);
    color: rgba(25, 211, 199, 0.9);
    border: 1px solid rgba(25, 211, 199, 0.3);
  }

  .status-banner.error {
    background: rgba(255, 77, 109, 0.12);
    color: rgba(255, 122, 122, 0.95);
    border: 1px solid rgba(255, 99, 132, 0.3);
  }

  .task-body {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .empty-items {
    padding: 1rem;
    border-radius: 0.75rem;
    background: rgba(255, 255, 255, 0.04);
    color: rgba(255, 255, 255, 0.55);
    text-align: center;
    font-size: 0.85rem;
  }

  .item {
    border-radius: 0.9rem;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
    overflow: hidden;
  }

  .item[data-status='active'] {
    border-color: rgba(25, 211, 199, 0.35);
    box-shadow: inset 0 0 0 1px rgba(25, 211, 199, 0.18);
  }

  .item[data-status='failure'] {
    border-color: rgba(255, 99, 132, 0.28);
    box-shadow: inset 0 0 0 1px rgba(255, 99, 132, 0.18);
  }

  .item-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.85rem 1rem;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    text-align: left;
    transition: background 0.2s ease;
  }

  .item-header:hover {
    background: rgba(255, 255, 255, 0.05);
  }

  .item-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 0.4rem;
    background: rgba(25, 211, 199, 0.18);
    color: rgba(25, 211, 199, 0.9);
    font-size: 0.8rem;
    font-weight: 600;
  }

  .item-title {
    flex: 1;
    font-size: 0.95rem;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
  }

  .item-chip {
    padding: 0.35rem 0.7rem;
    border-radius: 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.7);
  }

  .item-chip[data-status='success'],
  .item-chip[data-status='active'] {
    background: rgba(25, 211, 199, 0.18);
    color: rgba(25, 211, 199, 0.95);
  }

  .item-chip[data-status='failure'] {
    background: rgba(255, 99, 132, 0.18);
    color: rgba(255, 99, 132, 0.95);
  }

  .step-list {
    list-style: none;
    margin: 0;
    padding: 0.75rem 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  .step {
    display: flex;
    gap: 0.8rem;
    align-items: flex-start;
  }

  .step-marker {
    flex-shrink: 0;
    margin-top: 0.25rem;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
  }

  .step.active .step-marker,
  .step.success .step-marker {
    background: rgba(25, 211, 199, 0.8);
  }

  .step.active .step-marker {
    box-shadow: 0 0 0.35rem rgba(25, 211, 199, 0.7);
  }

  .step.failure .step-marker {
    background: rgba(255, 99, 132, 0.85);
    box-shadow: 0 0 0.35rem rgba(255, 99, 132, 0.5);
  }

  .step-content {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    flex: 1;
  }

  .step-label {
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.9);
    font-weight: 500;
  }

  .step-chip {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    padding: 0.2rem 0.6rem;
    border-radius: 0.6rem;
    font-size: 0.7rem;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.07);
    color: rgba(255, 255, 255, 0.7);
  }

  .step-chip[data-status='active'],
  .step-chip[data-status='success'] {
    background: rgba(25, 211, 199, 0.18);
    color: rgba(25, 211, 199, 0.95);
  }

  .step-chip[data-status='failure'] {
    background: rgba(255, 99, 132, 0.2);
    color: rgba(255, 99, 132, 0.95);
  }

  .step-message {
    font-size: 0.8rem;
    color: rgba(255, 255, 255, 0.6);
  }

  .dialog-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.5rem 1.25rem;
  }

  .footer-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.6);
  }

  .footer-indicator {
    padding: 0.25rem 0.65rem;
    border-radius: 0.65rem;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .footer-indicator.running {
    background: rgba(25, 211, 199, 0.18);
    color: rgba(25, 211, 199, 0.95);
  }

  .footer-indicator.failed {
    background: rgba(255, 99, 132, 0.18);
    color: rgba(255, 99, 132, 0.95);
  }

  .footer-indicator.done {
    background: rgba(103, 230, 158, 0.18);
    color: rgba(103, 230, 158, 0.95);
  }

  .action-button {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.75rem 1.6rem;
    border-radius: 0.75rem;
    font-size: 0.9rem;
    font-weight: 600;
    border: 1px solid rgba(25, 211, 199, 0.35);
    color: rgba(25, 211, 199, 0.92);
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.15), rgba(25, 211, 199, 0.05));
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .action-button:hover:not(:disabled) {
    border-color: rgba(25, 211, 199, 0.6);
    color: #0b2f32;
    background: linear-gradient(135deg, #19d3c7, #1dd1a1);
    box-shadow:
      0 0.35rem 1.25rem rgba(25, 211, 199, 0.35),
      inset 0 1px 0 rgba(255, 255, 255, 0.15);
  }

  .action-button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  @media (max-width: 960px) {
    .tasks-grid {
      grid-template-columns: repeat(1, minmax(0, 1fr));
    }
  }

  @media (max-width: 640px) {
    .dialog-body {
      padding: 1rem;
    }

    .content-region {
      padding-right: 0;
    }

    .task-progress {
      width: 6.5rem;
    }

    .item-header {
      flex-wrap: wrap;
    }

    .item-chip {
      margin-left: auto;
      margin-top: 0.35rem;
    }

    .dialog-footer {
      flex-direction: column;
      align-items: stretch;
    }

    .action-button {
      width: 100%;
    }

    .footer-status {
      justify-content: center;
    }
  }
</style>
