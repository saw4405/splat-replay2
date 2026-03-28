<script lang="ts">
  import { onDestroy } from 'svelte';
  import { fetchEditUploadStatus, updateEditUploadProcessOptions } from '../../api/assets';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import type { EditUploadStatus, ProgressEvent } from '../../api/types';
  import { Circle, Loader2, CheckCircle2, XCircle } from 'lucide-svelte';

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
    startedAt: number | null;
  }

  type PhaseStatus = 'pending' | 'active' | 'completed' | 'failed';
  interface Phase {
    label: string;
    status: PhaseStatus;
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
  let editUploadStatus: EditUploadStatus | null = null;
  let optionLoading = false;
  let optionSaving = false;
  let optionErrorMessage = '';
  let wasOpen = false;
  let statusRequestId = 0;

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
      { key: 'save', label: '保存・整理' },
    ],
    auto_upload: [
      { key: 'collect', label: 'ファイル情報収集' },
      { key: 'upload', label: '動画アップロード' },
      { key: 'caption', label: '字幕アップロード' },
      { key: 'thumb', label: 'サムネイルアップロード' },
      { key: 'playlist', label: 'プレイリスト追加' },
      { key: 'delete', label: 'ファイル削除' },
    ],
  };

  // defaultTaskSteps から stageKey → {key, label} のマッピングを自動生成
  // エイリアス（バックエンドが別キーで送るケース）もここで定義
  const stageKeyAliases: Record<string, Record<string, string>> = {
    auto_upload: { prepare: 'collect' },
  };

  const stageKeyMappings: Record<
    string,
    Record<string, { key: string; label: string }>
  > = Object.fromEntries(
    Object.entries(defaultTaskSteps).map(([taskId, steps]) => {
      const mapping: Record<string, { key: string; label: string }> = {};
      for (const step of steps) {
        mapping[step.key] = step;
      }
      const aliases = stageKeyAliases[taskId];
      if (aliases) {
        for (const [alias, targetKey] of Object.entries(aliases)) {
          const target = mapping[targetKey];
          if (target) {
            mapping[alias] = target;
          }
        }
      }
      return [taskId, mapping];
    })
  );

  const streamEventNames = ['progress_event', 'progress'];

  $: orderedTasks = taskOrder
    .map((id) => tasks[id])
    .filter((task): task is TaskState => Boolean(task));

  $: extraTasks = Object.values(tasks).filter((task) => !taskOrder.includes(task.id));

  $: taskList = [...orderedTasks, ...extraTasks];

  $: allFinished =
    taskList.length > 0 &&
    taskOrder.every((id) => tasks[id] !== undefined) &&
    taskList.every((task) => task.status === 'succeeded' || task.status === 'failed');

  $: anyRunning = taskList.some((task) => task.status === 'running');
  $: anyFailure = taskList.some((task) => task.status === 'failed');

  // フェーズステッパーの状態を導出
  $: phases = computePhases(tasks);

  // 経過時間の計測
  let elapsedTimers: Record<string, number> = {};
  let elapsedSeconds: Record<string, number> = {};

  // 完了サマリー
  $: totalItemsProcessed = taskList.reduce((sum, t) => sum + t.completed, 0);
  $: sleepAfterUploadEnabled = editUploadStatus?.sleepAfterUploadEffective ?? false;
  $: sleepToggleDisabled = optionLoading || optionSaving || !editUploadStatus || allFinished;

  $: if (isOpen) {
    ensureStream();
  } else {
    pauseStream();
  }

  $: if (isOpen !== wasOpen) {
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

  onDestroy(() => {
    disposeStream();
    Object.keys(elapsedTimers).forEach(stopElapsedTimer);
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
      startedAt: Date.now(),
    };
    tasks = { ...tasks, [taskId]: task };
    startElapsedTimer(taskId);
    if (isOpen && !optionSaving && (!editUploadStatus || editUploadStatus.state !== 'running')) {
      void loadEditUploadStatus();
    }
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
      ensureItemExists(draft, index, null);
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
          mapped?.label ?? 'ファイル情報収集',
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
    stopElapsedTimer(taskId);
    updateTask(taskId, event.task_name ?? undefined, (draft) => {
      const success = event.success !== false;
      draft.status = success ? 'succeeded' : 'failed';
      draft.completed =
        typeof event.completed === 'number' && Number.isFinite(event.completed)
          ? Math.max(0, event.completed)
          : draft.total;
      if (success) {
        const defaultMsg = `${draft.title}が完了しました。`;
        draft.successMessage = event.message ?? defaultMsg;
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
      startedAt: null,
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

  function manualReconnect(): void {
    if (!isOpen) {
      return;
    }
    shutdownStream(false);
    resetCountdown();
    openStream();
  }

  $: closeDisabled = anyRunning;

  function handleClose(): void {
    if (closeDisabled) {
      return;
    }
    isOpen = false;
  }

  function computePhases(taskMap: Record<string, TaskState>): Phase[] {
    const edit = taskMap['auto_edit'];
    const upload = taskMap['auto_upload'];

    let editStatus: PhaseStatus = 'pending';
    if (edit) {
      if (edit.status === 'running') editStatus = 'active';
      else if (edit.status === 'succeeded') editStatus = 'completed';
      else if (edit.status === 'failed') editStatus = 'failed';
    }

    let uploadStatus: PhaseStatus = 'pending';
    if (upload) {
      if (upload.status === 'running') uploadStatus = 'active';
      else if (upload.status === 'succeeded') uploadStatus = 'completed';
      else if (upload.status === 'failed') uploadStatus = 'failed';
    }

    let doneStatus: PhaseStatus = 'pending';
    if (edit && upload) {
      const editDone = edit.status === 'succeeded' || edit.status === 'failed';
      const uploadDone = upload.status === 'succeeded' || upload.status === 'failed';
      if (editDone && uploadDone) {
        const anyFail = edit.status === 'failed' || upload.status === 'failed';
        doneStatus = anyFail ? 'failed' : 'completed';
      }
    }

    return [
      { label: '編集', status: editStatus },
      { label: 'アップロード', status: uploadStatus },
      { label: '完了', status: doneStatus },
    ];
  }

  function startElapsedTimer(taskId: string): void {
    if (elapsedTimers[taskId]) return;
    elapsedSeconds = { ...elapsedSeconds, [taskId]: 0 };
    const startTime = Date.now();
    elapsedTimers[taskId] = window.setInterval(() => {
      elapsedSeconds = {
        ...elapsedSeconds,
        [taskId]: Math.floor((Date.now() - startTime) / 1000),
      };
    }, 1000);
  }

  function stopElapsedTimer(taskId: string): void {
    if (elapsedTimers[taskId]) {
      clearInterval(elapsedTimers[taskId]);
      delete elapsedTimers[taskId];
    }
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
  on:close={handleClose}
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
        <button type="button" class="retry-button" on:click={manualReconnect}>再接続</button>
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
            />
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
                aria-valuenow={taskProgress(task)}
              >
                <div class="task-progress-fill" style={`width: ${taskProgress(task)}%`} />
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

  <footer slot="footer" class="dialog-footer">
    <!-- スリープトグル -->
    <div class="footer-option">
      <label class="sleep-toggle" class:disabled={sleepToggleDisabled}>
        <input
          type="checkbox"
          checked={sleepAfterUploadEnabled}
          disabled={sleepToggleDisabled}
          aria-label="完了後スリープ"
          on:change={handleSleepAfterUploadChange}
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
        on:click={handleClose}
        disabled={closeDisabled}
        title={closeDisabled ? '処理中は閉じることができません' : ''}
      >
        閉じる
      </button>
    </div>
  </footer>
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
