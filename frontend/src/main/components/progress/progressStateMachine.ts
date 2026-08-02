/**
 * 進捗状態マシン
 *
 * ProgressDialog から抽出した純粋な TypeScript ロジック。
 * Svelte ランタイムに依存しないため、単体テストが可能。
 */

import type { ProgressEvent, GroupPayload, VideoAssetPayload } from '../../api/types';

// --- 型定義 ---

export type ConnectionState = 'idle' | 'connecting' | 'open' | 'error';
export type TaskStatus = 'idle' | 'running' | 'succeeded' | 'failed';
export type ItemStatus = 'pending' | 'active' | 'success' | 'failure';
export type StepStatus = ItemStatus;

export interface StepState {
  key: string;
  label: string;
  status: StepStatus;
  message: string | null;
}

export interface ItemState {
  title: string;
  status: ItemStatus;
  steps: StepState[];
  activeStepKey: string | null;
  expanded: boolean;
  clips?: GroupPayload | null;
  dismissed?: boolean;
}

export interface TaskState {
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
  progressPercent: number | null;
}

export type PhaseStatus = 'pending' | 'active' | 'completed' | 'failed';

export interface Phase {
  label: string;
  status: PhaseStatus;
}

// --- 設定定数 ---

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

// バックエンドが別キーで送るケースのエイリアス定義
const stageKeyAliases: Record<string, Record<string, string>> = {
  auto_upload: { prepare: 'collect' },
};

// defaultTaskSteps から stageKey → {key, label} のマッピングを自動生成
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

// --- 状態マシン本体 ---

/**
 * 進捗イベントを受け取りタスク状態を管理するクラス。
 * Svelte ランタイムに依存しないため、単体テストが可能。
 * Svelte コンポーネントから利用する際は tasksVersion パターンで
 * リアクティビティをトリガーする。
 */
export class ProgressStateMachine {
  private _tasks: Record<string, TaskState> = {};
  private _elapsedTimers: Record<string, ReturnType<typeof setInterval>> = {};
  private _elapsedSeconds: Record<string, number> = {};

  // --- ゲッター ---

  get tasks(): Record<string, TaskState> {
    return this._tasks;
  }

  get taskList(): TaskState[] {
    const ordered = taskOrder
      .map((id) => this._tasks[id])
      .filter((task): task is TaskState => Boolean(task));
    const extra = Object.values(this._tasks).filter((task) => !taskOrder.includes(task.id));
    return [...ordered, ...extra];
  }

  get allFinished(): boolean {
    const list = this.taskList;
    return (
      list.length > 0 &&
      taskOrder.every((id) => this._tasks[id] !== undefined) &&
      list.every((task) => task.status === 'succeeded' || task.status === 'failed')
    );
  }

  get anyRunning(): boolean {
    return this.taskList.some((task) => task.status === 'running');
  }

  get anyFailure(): boolean {
    return this.taskList.some((task) => task.status === 'failed');
  }

  get phases(): Phase[] {
    return this._computePhases(this._tasks);
  }

  get totalItemsProcessed(): number {
    return this.taskList.reduce((sum, t) => sum + t.completed, 0);
  }

  // --- 公開メソッド ---

  /** 進捗イベントを適用し内部状態を更新する */
  applyEvent(event: ProgressEvent): void {
    switch (event.kind) {
      case 'start':
        this._handleStart(event);
        break;
      case 'items':
        this._handleItems(event);
        break;
      case 'item_stage':
        this._handleItemStage(event);
        break;
      case 'item_finish':
        this._handleItemFinish(event);
        break;
      case 'stage':
        this._handleStage(event);
        break;
      case 'total':
        this._handleTotal(event);
        break;
      case 'advance':
        this._handleAdvance(event);
        break;
      case 'finish':
        this._handleFinish(event);
        break;
      default:
        break;
    }

    // イベントに進捗率が含まれていればタスク状態に反映
    if (event.progress_percent !== undefined && event.progress_percent !== null) {
      const task = this._tasks[event.task_id];
      if (task) {
        task.progressPercent = event.progress_percent;
        task.lastUpdated = Date.now();
      }
    }
  }

  /** タスクの進捗率（0〜100）を返す */
  taskProgress(taskId: string): number {
    const task = this._tasks[taskId];
    if (!task) {
      return 0;
    }
    if (task.progressPercent !== undefined && task.progressPercent !== null) {
      return task.progressPercent;
    }
    if (task.total <= 0) {
      return 0;
    }
    const ratio = Math.max(0, Math.min(1, task.completed / task.total));
    return Math.round(ratio * 100);
  }

  /** タスクの経過秒数を返す */
  getElapsedSeconds(taskId: string): number {
    return this._elapsedSeconds[taskId] ?? 0;
  }

  /** 経過時間タイマーを開始する */
  startElapsedTimer(taskId: string): void {
    if (this._elapsedTimers[taskId]) {
      return;
    }
    this._elapsedSeconds = { ...this._elapsedSeconds, [taskId]: 0 };
    const startTime = Date.now();
    this._elapsedTimers[taskId] = setInterval(() => {
      this._elapsedSeconds = {
        ...this._elapsedSeconds,
        [taskId]: Math.floor((Date.now() - startTime) / 1000),
      };
    }, 1000);
  }

  /** 経過時間タイマーを停止する */
  stopElapsedTimer(taskId: string): void {
    const timer = this._elapsedTimers[taskId];
    if (timer !== undefined) {
      clearInterval(timer);
      delete this._elapsedTimers[taskId];
    }
  }

  /** 全状態をリセットする */
  reset(): void {
    this.dispose();
    this._tasks = {};
    this._elapsedSeconds = {};
  }

  /** 全タイマーを停止してリソースを解放する */
  dispose(): void {
    Object.keys(this._elapsedTimers).forEach((taskId) => this.stopElapsedTimer(taskId));
  }

  // --- プライベートメソッド: イベントハンドラ ---

  private _handleStart(event: ProgressEvent): void {
    const taskId = event.task_id;
    const title = this._formatTaskTitle(taskId, event.task_name);
    const items = Array.isArray(event.items) ? event.items : [];
    const clips = Array.isArray(event.clips) ? event.clips : [];
    const createdItems = items.map((itemTitle, index) => {
      const item = this._makeItem(taskId, itemTitle, index === 0);
      const matchedClip = clips.find((c) => c.group_index === index);
      if (matchedClip) {
        item.clips = matchedClip;
      }
      return item;
    });
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
      progressPercent: event.progress_percent ?? null,
    };
    this._tasks = { ...this._tasks, [taskId]: task };
    this.startElapsedTimer(taskId);
  }

  private _handleItems(event: ProgressEvent): void {
    const taskId = event.task_id;
    if (!Array.isArray(event.items)) {
      return;
    }
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
      event.items!.forEach((title, index) => {
        if (draft.items[index]) {
          if (!draft.items[index].title || draft.items[index].title.startsWith('アイテム')) {
            draft.items[index].title = title;
          }
        } else {
          draft.items.push(this._makeItem(taskId, title, false));
        }
      });
      if (draft.total === 0) {
        draft.total = event.items!.length;
      }
    });
  }

  private _handleItemStage(event: ProgressEvent): void {
    const taskId = event.task_id;
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
      const index =
        typeof event.item_index === 'number' && event.item_index >= 0
          ? event.item_index
          : (draft.activeIndex ?? draft.items.length);
      if (index < 0) {
        return;
      }
      this._ensureItemExists(draft, index, null);
      this._setActiveItem(draft, index);
      const item = draft.items[index];
      const mapped = this._mapStageKey(taskId, event.item_key ?? '');
      const stepKey = mapped?.key ?? event.item_key ?? `step_${item.steps.length}`;
      const stepLabel = mapped?.label ?? event.item_label ?? this._defaultStepLabel(stepKey);
      this._setActiveStep(item, stepKey, stepLabel, event.message ?? null);
      if (taskId === 'auto_edit' && stepKey === 'save' && event.message?.trim()) {
        item.title = event.message.trim();
      }
      draft.status = 'running';
      if (event.progress_percent === undefined || event.progress_percent === null) {
        draft.progressPercent = null;
      }
    });
  }

  private _handleItemFinish(event: ProgressEvent): void {
    const taskId = event.task_id;
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
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
        this._markItemSuccess(item);
        // 保存・整理フェーズが完了したことを表すために退場フラグを立てる
        item.dismissed = true;
      } else {
        this._markItemFailure(item, event.message ?? null);
      }
      draft.activeIndex = success ? this._pickNextIndex(draft, index) : index;
    });
  }

  private _handleStage(event: ProgressEvent): void {
    const taskId = event.task_id;
    const stageKey = event.stage_key ?? '';
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
      if (taskId === 'auto_edit' && stageKey === 'edit_group') {
        const title = this._pickStageTitle(event);
        const index = this._findItemIndexByTitle(draft, title);
        const targetIndex =
          index >= 0 ? index : draft.items.push(this._makeItem(taskId, title, false)) - 1;
        this._setActiveItem(draft, targetIndex);
        draft.items[targetIndex].title = title;
        return;
      }
      if (taskId === 'auto_upload' && stageKey === 'prepare') {
        const title = this._pickStageTitle(event);
        const index = this._findItemIndexByTitle(draft, title);
        const targetIndex =
          index >= 0 ? index : draft.items.push(this._makeItem(taskId, title, false)) - 1;
        this._setActiveItem(draft, targetIndex);
        draft.items[targetIndex].title = title;
        const mapped = this._mapStageKey(taskId, 'collect');
        this._setActiveStep(
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
      const mapped = this._mapStageKey(taskId, stageKey);
      const stepKey = mapped?.key ?? stageKey;
      const stepLabel = mapped?.label ?? event.stage_label ?? this._defaultStepLabel(stepKey);
      this._setActiveStep(current, stepKey, stepLabel, event.message ?? null);
      if (event.progress_percent === undefined || event.progress_percent === null) {
        draft.progressPercent = null;
      }
    });
  }

  private _handleTotal(event: ProgressEvent): void {
    const taskId = event.task_id;
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
      if (typeof event.total === 'number' && Number.isFinite(event.total)) {
        draft.total = Math.max(0, event.total);
      }
    });
  }

  private _handleAdvance(event: ProgressEvent): void {
    const taskId = event.task_id;
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
      const previousCompleted = draft.completed;
      if (typeof event.completed === 'number' && Number.isFinite(event.completed)) {
        draft.completed = Math.max(0, event.completed);
      } else if (
        draft.total > 0 &&
        (event.progress_percent === undefined || event.progress_percent === null)
      ) {
        draft.completed = Math.min(draft.total, draft.completed + 1);
      }
      const completedAdvanced = draft.completed > previousCompleted;
      if (completedAdvanced && draft.activeIndex !== null && draft.items[draft.activeIndex]) {
        const item = draft.items[draft.activeIndex];
        this._markItemSuccess(item);
        item.dismissed = true;
        draft.activeIndex = this._pickNextIndex(draft, draft.activeIndex);
      }
    });
  }

  private _handleFinish(event: ProgressEvent): void {
    const taskId = event.task_id;
    this.stopElapsedTimer(taskId);
    this._updateTask(taskId, event.task_name ?? undefined, (draft) => {
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
            this._markItemSuccess(item);
          }
        });
        draft.activeIndex = null;
      } else {
        draft.errorMessage = event.message ?? '処理に失敗しました。';
        if (draft.activeIndex !== null && draft.items[draft.activeIndex]) {
          this._markItemFailure(draft.items[draft.activeIndex], event.message ?? null);
        }
        draft.successMessage = null;
      }
    });
  }

  // --- プライベートメソッド: ヘルパー ---

  private _markItemSuccess(item: ItemState): void {
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

  private _markItemFailure(item: ItemState, message: string | null): void {
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

  private _setActiveItem(task: TaskState, index: number): void {
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

  private _setActiveStep(
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

  private _ensureItemExists(task: TaskState, index: number, titleHint: string | null): void {
    while (task.items.length <= index) {
      task.items.push(
        this._makeItem(task.id, this._defaultItemTitle(task.id, task.items.length), false)
      );
    }
    const item = task.items[index];
    if (titleHint && titleHint.trim().length > 0) {
      item.title = titleHint.trim();
    }
  }

  private _pickNextIndex(task: TaskState, currentIndex: number): number | null {
    const nextIndex = currentIndex + 1;
    return nextIndex < task.items.length ? nextIndex : null;
  }

  private _defaultItemTitle(taskId: string, index: number): string {
    const base = taskLabels[taskId] ?? 'アイテム';
    return `${base} ${index + 1}`;
  }

  private _defaultTaskTitle(taskId: string): string {
    return taskLabels[taskId] ?? taskId;
  }

  private _formatTaskTitle(taskId: string, provided?: string | null): string {
    if (provided && provided.trim().length > 0) {
      return provided.trim();
    }
    return this._defaultTaskTitle(taskId);
  }

  private _createDefaultSteps(taskId: string): StepState[] {
    const defs = defaultTaskSteps[taskId];
    if (!defs) {
      return [];
    }
    return defs.map((def) => ({
      key: def.key,
      label: def.label,
      status: 'pending' as StepStatus,
      message: null,
    }));
  }

  private _makeItem(taskId: string, title: string, active: boolean): ItemState {
    return {
      title: title || this._defaultItemTitle(taskId, 0),
      status: active ? 'active' : 'pending',
      steps: this._createDefaultSteps(taskId),
      activeStepKey: null,
      expanded: active,
    };
  }

  private _mapStageKey(taskId: string, key: string): { key: string; label: string } | null {
    if (!key) {
      return null;
    }
    const mapping = stageKeyMappings[taskId];
    if (!mapping) {
      return null;
    }
    return mapping[key] ?? null;
  }

  private _defaultStepLabel(key: string): string {
    if (!key) {
      return '処理';
    }
    return key.replace(/_/g, ' ');
  }

  private _pickStageTitle(event: ProgressEvent): string {
    return (
      (event.stage_label && event.stage_label.trim()) ||
      (event.message && String(event.message).trim()) ||
      this._defaultItemTitle(event.task_id, 0)
    );
  }

  private _findItemIndexByTitle(task: TaskState, title: string): number {
    if (!title) {
      return -1;
    }
    return task.items.findIndex((item) => item.title === title);
  }

  private _cloneTask(task: TaskState): TaskState {
    return {
      ...task,
      items: task.items.map((item) => ({
        ...item,
        steps: item.steps.map((step) => ({ ...step })),
        clips: item.clips
          ? {
              ...item.clips,
              video_assets: item.clips.video_assets.map((v: VideoAssetPayload) => ({ ...v })),
            }
          : null,
        dismissed: item.dismissed,
      })),
    };
  }

  private _updateTask(
    taskId: string,
    fallbackTitle: string | undefined,
    mutator: (draft: TaskState) => void
  ): TaskState {
    const current = this._tasks[taskId] ?? {
      id: taskId,
      title: this._formatTaskTitle(taskId, fallbackTitle),
      total: 0,
      completed: 0,
      status: 'idle' as TaskStatus,
      items: [],
      activeIndex: null,
      errorMessage: null,
      successMessage: null,
      lastUpdated: Date.now(),
      startedAt: null,
      progressPercent: null,
    };

    const draft = this._cloneTask(current);
    if ((!draft.title || draft.title === current.title) && fallbackTitle) {
      draft.title = this._formatTaskTitle(taskId, fallbackTitle);
    }
    mutator(draft);
    draft.lastUpdated = Date.now();
    this._tasks = { ...this._tasks, [taskId]: draft };
    return draft;
  }

  private _computePhases(taskMap: Record<string, TaskState>): Phase[] {
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
}
