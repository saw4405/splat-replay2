/**
 * ProgressStateMachine のロジックテスト
 *
 * 純粋な TypeScript クラスのため、Svelte ランタイムなしで実行可能。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProgressStateMachine } from './progressStateMachine';
import type { ProgressEvent } from '../../api/types';

// --- テストヘルパー ---

function makeEvent(
  overrides: Partial<ProgressEvent> & { task_id: string; kind: ProgressEvent['kind'] }
): ProgressEvent {
  return {
    task_id: overrides.task_id,
    kind: overrides.kind,
    task_name: overrides.task_name ?? '',
    total: overrides.total ?? null,
    completed: overrides.completed ?? null,
    stage_key: overrides.stage_key ?? null,
    stage_label: overrides.stage_label ?? null,
    stage_index: overrides.stage_index ?? null,
    stage_count: overrides.stage_count ?? null,
    success: overrides.success ?? null,
    message: overrides.message ?? null,
    items: overrides.items ?? null,
    item_index: overrides.item_index ?? null,
    item_key: overrides.item_key ?? null,
    item_label: overrides.item_label ?? null,
    progress_percent: overrides.progress_percent ?? null,
    clips: overrides.clips ?? null,
  };
}

// --- テスト ---

describe('ProgressStateMachine', () => {
  let sm: ProgressStateMachine;

  beforeEach(() => {
    sm = new ProgressStateMachine();
  });

  afterEach(() => {
    sm.dispose();
    vi.clearAllTimers();
    vi.restoreAllMocks();
  });

  // =========================================================
  // 初期状態
  // =========================================================

  describe('初期状態', () => {
    it('tasks が空オブジェクト', () => {
      expect(sm.tasks).toEqual({});
    });

    it('taskList が空配列', () => {
      expect(sm.taskList).toEqual([]);
    });

    it('allFinished が false', () => {
      expect(sm.allFinished).toBe(false);
    });

    it('anyRunning が false', () => {
      expect(sm.anyRunning).toBe(false);
    });

    it('anyFailure が false', () => {
      expect(sm.anyFailure).toBe(false);
    });

    it('totalItemsProcessed が 0', () => {
      expect(sm.totalItemsProcessed).toBe(0);
    });

    it('phases が全て pending', () => {
      const phases = sm.phases;
      expect(phases).toHaveLength(3);
      expect(phases[0].status).toBe('pending');
      expect(phases[1].status).toBe('pending');
      expect(phases[2].status).toBe('pending');
    });
  });

  // =========================================================
  // start イベント
  // =========================================================

  describe('start イベント', () => {
    it('タスクを作成しステータスを running に設定する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));

      const task = sm.tasks['auto_edit'];
      expect(task).toBeDefined();
      expect(task.status).toBe('running');
      expect(task.id).toBe('auto_edit');
    });

    it('task_name が空の場合はデフォルトラベルをタイトルに使用する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', task_name: '' }));
      expect(sm.tasks['auto_edit'].title).toBe('自動編集');
    });

    it('task_name が指定された場合はそのタイトルを使用する', () => {
      sm.applyEvent(
        makeEvent({ task_id: 'auto_edit', kind: 'start', task_name: 'カスタムタイトル' })
      );
      expect(sm.tasks['auto_edit'].title).toBe('カスタムタイトル');
    });

    it('items が指定された場合はアイテムを作成する', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B', '動画C'],
          total: 3,
        })
      );

      const task = sm.tasks['auto_edit'];
      expect(task.items).toHaveLength(3);
      expect(task.items[0].title).toBe('動画A');
      expect(task.items[1].title).toBe('動画B');
      expect(task.items[2].title).toBe('動画C');
    });

    it('最初のアイテムが active、残りが pending', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B'],
        })
      );

      const task = sm.tasks['auto_edit'];
      expect(task.items[0].status).toBe('active');
      expect(task.items[1].status).toBe('pending');
      expect(task.activeIndex).toBe(0);
    });

    it('total と completed を正しく設定する', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B'],
          total: 5,
          completed: 2,
        })
      );

      const task = sm.tasks['auto_edit'];
      expect(task.total).toBe(5);
      expect(task.completed).toBe(2);
    });

    it('items が空の場合は activeIndex が null', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', items: [] }));
      expect(sm.tasks['auto_edit'].activeIndex).toBeNull();
    });
  });

  // =========================================================
  // items イベント
  // =========================================================

  describe('items イベント', () => {
    beforeEach(() => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', items: ['動画A'] }));
    });

    it('デフォルトタイトルのアイテムは items イベントで更新される', () => {
      // items イベントは「アイテム」で始まるデフォルトタイトルのみ更新する
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', items: [] }));
      // start で items 空 → アイテムなし。items イベントでアイテム追加
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'items', items: ['更新済み動画A'] }));
      // items が足りない分は末尾に追加される
      expect(sm.tasks['auto_edit'].items[0].title).toBe('更新済み動画A');
    });

    it('既にカスタムタイトルが付いたアイテムは items イベントで上書きされない', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'items', items: ['更新済み動画A'] }));
      // 「動画A」は「アイテム」で始まらないのでタイトルは変わらない
      expect(sm.tasks['auto_edit'].items[0].title).toBe('動画A');
    });

    it('不足しているアイテムを末尾に追加する', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'items',
          items: ['動画A', '動画B', '動画C'],
        })
      );
      expect(sm.tasks['auto_edit'].items).toHaveLength(3);
      expect(sm.tasks['auto_edit'].items[2].title).toBe('動画C');
    });

    it('total が 0 の場合は items 数で更新する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'items', items: ['動画A', '動画B'] }));
      expect(sm.tasks['auto_edit'].total).toBe(2);
    });
  });

  // =========================================================
  // stage イベント
  // =========================================================

  describe('stage イベント', () => {
    beforeEach(() => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', items: ['動画A'], total: 1 }));
    });

    it('アクティブアイテムにステップを設定する', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'stage',
          stage_key: 'concat',
          stage_label: '動画結合',
        })
      );

      const item = sm.tasks['auto_edit'].items[0];
      const step = item.steps.find((s) => s.key === 'concat');
      expect(step?.status).toBe('active');
      expect(item.activeStepKey).toBe('concat');
    });

    it('auto_edit + edit_group ではアイテムを生成してアクティブにする', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'stage',
          stage_key: 'edit_group',
          stage_label: 'グループ動画',
        })
      );

      const task = sm.tasks['auto_edit'];
      const activeItem = task.items[task.activeIndex!];
      expect(activeItem.title).toBe('グループ動画');
      expect(activeItem.status).toBe('active');
    });
  });

  // =========================================================
  // item_stage イベント
  // =========================================================

  describe('item_stage イベント', () => {
    beforeEach(() => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B'],
          total: 2,
        })
      );
    });

    it('item_index で指定したアイテムをアクティブにする', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_stage',
          item_index: 1,
          item_key: 'concat',
          item_label: '動画結合',
        })
      );

      const task = sm.tasks['auto_edit'];
      expect(task.activeIndex).toBe(1);
      expect(task.items[1].status).toBe('active');
    });

    it('ステップをアクティブにする', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_stage',
          item_index: 0,
          item_key: 'subtitle',
          item_label: '字幕編集',
        })
      );

      const item = sm.tasks['auto_edit'].items[0];
      expect(item.activeStepKey).toBe('subtitle');
      const step = item.steps.find((s) => s.key === 'subtitle');
      expect(step?.status).toBe('active');
    });

    it('進捗率なしでステージが切り替わった場合は前ステージの進捗率を引き継がない', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_stage',
          item_index: 0,
          item_key: 'concat',
          item_label: '動画結合',
          progress_percent: 100,
        })
      );
      expect(sm.tasks['auto_edit'].progressPercent).toBe(100);

      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_stage',
          item_index: 0,
          item_key: 'thumbnail',
          item_label: 'サムネイル編集',
          message: 'サムネイル画像を生成中',
          progress_percent: null,
        })
      );

      expect(sm.tasks['auto_edit'].progressPercent).toBeNull();
    });

    it('auto_edit の保存ステージでは message を完了カード用タイトルとして保持する', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_stage',
          item_index: 0,
          item_key: 'save',
          item_label: '保存・整理',
          message: '【ガチヤグラ】海女美術大学の軌跡',
        })
      );

      expect(sm.tasks['auto_edit'].items[0].title).toBe('【ガチヤグラ】海女美術大学の軌跡');
    });
  });

  // =========================================================
  // item_finish イベント
  // =========================================================

  describe('item_finish イベント', () => {
    beforeEach(() => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B'],
          total: 2,
        })
      );
    });

    it('success=true でアイテムを success にマークする', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_finish',
          item_index: 0,
          success: true,
        })
      );

      expect(sm.tasks['auto_edit'].items[0].status).toBe('success');
      expect(sm.tasks['auto_edit'].items[0].expanded).toBe(false);
    });

    it('success=false でアイテムを failure にマークする', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_finish',
          item_index: 0,
          success: false,
          message: 'エラーが発生しました',
        })
      );

      expect(sm.tasks['auto_edit'].items[0].status).toBe('failure');
      expect(sm.tasks['auto_edit'].items[0].expanded).toBe(true);
    });

    it('成功後は activeIndex を次のアイテムに進める', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_finish',
          item_index: 0,
          success: true,
        })
      );

      expect(sm.tasks['auto_edit'].activeIndex).toBe(1);
    });

    it('最後のアイテム成功後は activeIndex が null', () => {
      sm.applyEvent(
        makeEvent({ task_id: 'auto_edit', kind: 'item_finish', item_index: 0, success: true })
      );
      sm.applyEvent(
        makeEvent({ task_id: 'auto_edit', kind: 'item_finish', item_index: 1, success: true })
      );

      expect(sm.tasks['auto_edit'].activeIndex).toBeNull();
    });
  });

  // =========================================================
  // advance イベント
  // =========================================================

  describe('advance イベント', () => {
    beforeEach(() => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B'],
          total: 2,
          completed: 0,
        })
      );
    });

    it('completed を指定値に更新する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'advance', completed: 1 }));
      expect(sm.tasks['auto_edit'].completed).toBe(1);
    });

    it('completed が未指定の場合は +1 インクリメント', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'advance' }));
      expect(sm.tasks['auto_edit'].completed).toBe(1);
    });

    it('アクティブアイテムを success にマークし次へ進める', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'advance', completed: 1 }));

      expect(sm.tasks['auto_edit'].items[0].status).toBe('success');
      expect(sm.tasks['auto_edit'].activeIndex).toBe(1);
    });

    it('advance で成功したアイテムの dismissed が true になる', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'advance', completed: 1 }));

      expect(sm.tasks['auto_edit'].items[0].dismissed).toBe(true);
    });

    it('進捗率だけの advance ではアクティブアイテムを完了扱いにしない', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'advance',
          completed: 0,
          progress_percent: 50,
        })
      );

      expect(sm.tasks['auto_edit'].items[0].status).toBe('active');
      expect(sm.tasks['auto_edit'].items[0].dismissed).toBeUndefined();
      expect(sm.tasks['auto_edit'].activeIndex).toBe(0);
    });
  });

  // =========================================================
  // finish イベント
  // =========================================================

  describe('finish イベント', () => {
    beforeEach(() => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A'],
          total: 1,
        })
      );
    });

    it('success=true でタスクを succeeded に設定する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));
      expect(sm.tasks['auto_edit'].status).toBe('succeeded');
    });

    it('success=false でタスクを failed に設定する', () => {
      sm.applyEvent(
        makeEvent({ task_id: 'auto_edit', kind: 'finish', success: false, message: '失敗' })
      );
      expect(sm.tasks['auto_edit'].status).toBe('failed');
      expect(sm.tasks['auto_edit'].errorMessage).toBe('失敗');
    });

    it('成功時は successMessage を設定する', () => {
      sm.applyEvent(
        makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true, message: '完了！' })
      );
      expect(sm.tasks['auto_edit'].successMessage).toBe('完了！');
      expect(sm.tasks['auto_edit'].errorMessage).toBeNull();
    });

    it('成功時に message が未指定の場合はデフォルトメッセージを設定する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));
      expect(sm.tasks['auto_edit'].successMessage).toContain('完了しました');
    });

    it('成功時は未完了のアイテムを success にマークする', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));

      const items = sm.tasks['auto_edit'].items;
      items.forEach((item) => {
        expect(item.status).toBe('success');
      });
    });

    it('成功時は activeIndex が null になる', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));
      expect(sm.tasks['auto_edit'].activeIndex).toBeNull();
    });
  });

  // =========================================================
  // タスク順序
  // =========================================================

  describe('タスク順序', () => {
    it('taskOrder に従って auto_edit → auto_upload の順で並ぶ', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));

      const list = sm.taskList;
      expect(list[0].id).toBe('auto_edit');
      expect(list[1].id).toBe('auto_upload');
    });

    it('未知のタスク ID は末尾に追加される', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'custom_task', kind: 'start' }));

      const list = sm.taskList;
      expect(list[list.length - 1].id).toBe('custom_task');
    });

    it('未知のタスク ID でもデフォルト状態のタスクが生成される', () => {
      sm.applyEvent(makeEvent({ task_id: 'unknown_task', kind: 'start' }));

      const task = sm.tasks['unknown_task'];
      expect(task).toBeDefined();
      expect(task.id).toBe('unknown_task');
      expect(task.title).toBe('unknown_task');
    });
  });

  // =========================================================
  // フェーズ計算
  // =========================================================

  describe('フェーズ計算', () => {
    it('auto_edit が running なら編集フェーズは active', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));

      const phases = sm.phases;
      expect(phases[0].label).toBe('編集');
      expect(phases[0].status).toBe('active');
    });

    it('auto_edit 完了後は編集フェーズが completed', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));

      expect(sm.phases[0].status).toBe('completed');
    });

    it('auto_edit が failed なら編集フェーズは failed', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: false }));

      expect(sm.phases[0].status).toBe('failed');
    });

    it('両タスクが completed なら完了フェーズが completed', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'finish', success: true }));

      expect(sm.phases[2].label).toBe('完了');
      expect(sm.phases[2].status).toBe('completed');
    });

    it('一方が failed なら完了フェーズは failed', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: false }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'finish', success: true }));

      expect(sm.phases[2].status).toBe('failed');
    });
  });

  // =========================================================
  // allFinished / anyRunning / anyFailure
  // =========================================================

  describe('allFinished', () => {
    it('全タスクが succeeded なら true', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'finish', success: true }));

      expect(sm.allFinished).toBe(true);
    });

    it('一方が failed でも両方終了なら true', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: false }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'finish', success: true }));

      expect(sm.allFinished).toBe(true);
    });

    it('一部がまだ running なら false', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));

      expect(sm.allFinished).toBe(false);
    });

    it('auto_upload だけのタスクでは taskOrder 未充足で false', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'finish', success: true }));

      expect(sm.allFinished).toBe(false);
    });
  });

  describe('anyRunning / anyFailure', () => {
    it('running タスクがあれば anyRunning が true', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      expect(sm.anyRunning).toBe(true);
    });

    it('全タスク完了後は anyRunning が false', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));
      expect(sm.anyRunning).toBe(false);
    });

    it('failed タスクがあれば anyFailure が true', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: false }));
      expect(sm.anyFailure).toBe(true);
    });
  });

  // =========================================================
  // taskProgress
  // =========================================================

  describe('taskProgress', () => {
    it('completed/total から進捗率を計算する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', total: 4, completed: 0 }));
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'advance', completed: 1 }));

      expect(sm.taskProgress('auto_edit')).toBe(25);
    });

    it('total が 0 なら 0 を返す', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      expect(sm.taskProgress('auto_edit')).toBe(0);
    });

    it('存在しないタスク ID なら 0 を返す', () => {
      expect(sm.taskProgress('nonexistent')).toBe(0);
    });

    it('completed === total なら 100 を返す', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', total: 3, completed: 3 }));
      expect(sm.taskProgress('auto_edit')).toBe(100);
    });
  });

  // =========================================================
  // 経過時間タイマー
  // =========================================================

  describe('経過時間タイマー', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('start イベント後に経過秒が増加する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      expect(sm.getElapsedSeconds('auto_edit')).toBe(0);

      vi.advanceTimersByTime(3000);
      expect(sm.getElapsedSeconds('auto_edit')).toBe(3);
    });

    it('finish イベント後はタイマーが停止する', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      vi.advanceTimersByTime(2000);
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'finish', success: true }));

      const elapsed = sm.getElapsedSeconds('auto_edit');
      vi.advanceTimersByTime(5000);
      expect(sm.getElapsedSeconds('auto_edit')).toBe(elapsed);
    });

    it('stopElapsedTimer 後は秒数が増えない', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      vi.advanceTimersByTime(1000);
      sm.stopElapsedTimer('auto_edit');
      const elapsed = sm.getElapsedSeconds('auto_edit');

      vi.advanceTimersByTime(5000);
      expect(sm.getElapsedSeconds('auto_edit')).toBe(elapsed);
    });

    it('存在しないタスクの elapsed は 0', () => {
      expect(sm.getElapsedSeconds('nonexistent')).toBe(0);
    });
  });

  // =========================================================
  // reset / dispose
  // =========================================================

  describe('reset / dispose', () => {
    it('reset で全タスク状態がクリアされる', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));

      sm.reset();

      expect(sm.tasks).toEqual({});
      expect(sm.taskList).toHaveLength(0);
    });

    it('dispose 後はタイマーが全て停止する', () => {
      vi.useFakeTimers();
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start' }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start' }));
      vi.advanceTimersByTime(2000);

      sm.dispose();
      const elapsed = sm.getElapsedSeconds('auto_edit');
      vi.advanceTimersByTime(5000);

      expect(sm.getElapsedSeconds('auto_edit')).toBe(elapsed);
      vi.useRealTimers();
    });
  });

  // =========================================================
  // エッジケース
  // =========================================================

  describe('エッジケース', () => {
    it('未知の kind は何も起こらない', () => {
      const event = makeEvent({ task_id: 'auto_edit', kind: 'start' });
      // @ts-expect-error - 未知のイベント種別テスト
      event.kind = 'unknown_kind';
      expect(() => sm.applyEvent(event)).not.toThrow();
    });

    it('stage イベントを未開始タスクに送ると idle タスクが作成される', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'stage', stage_key: 'concat' }));
      expect(sm.tasks['auto_edit']).toBeDefined();
      expect(sm.tasks['auto_edit'].status).toBe('idle');
    });

    it('stageKeyAlias: prepare は auto_upload では collect にマップされる', () => {
      sm.applyEvent(
        makeEvent({ task_id: 'auto_upload', kind: 'start', items: ['動画A'], total: 1 })
      );
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_upload',
          kind: 'stage',
          stage_key: 'prepare',
          stage_label: '動画A',
        })
      );

      const item = sm.tasks['auto_upload'].items[0];
      // prepare は collect にエイリアスされるため collect ステップがアクティブになる
      expect(item.activeStepKey).toBe('collect');
    });

    it('totalItemsProcessed は全タスクの completed 合計を返す', () => {
      sm.applyEvent(makeEvent({ task_id: 'auto_edit', kind: 'start', total: 3, completed: 2 }));
      sm.applyEvent(makeEvent({ task_id: 'auto_upload', kind: 'start', total: 2, completed: 1 }));

      expect(sm.totalItemsProcessed).toBe(3);
    });

    it('start イベントで clips が与えられたとき対応するアイテムにバインドされる', () => {
      const mockClips = [
        {
          group_index: 0,
          date_label: '6/27\n11:00～',
          match_name: 'バンカラマッチ',
          rule_name: 'ガチエリア',
          video_assets: [
            {
              video_id: 'recorded/video1.mp4',
              duration_seconds: 300,
              judgement: 'WIN',
              stage_name: 'ザトウマーケット',
              kill: 12,
              death: 4,
              special: 3,
              gold_medals: 2,
              silver_medals: 1,
              rate: { type: 'XP', value: '2100.5' },
            },
          ],
        },
      ];

      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['グループ1'],
          // @ts-expect-error - テストで clips を渡す
          clips: mockClips,
        })
      );

      const item = sm.tasks['auto_edit'].items[0];
      expect(item.clips).toBeDefined();
      expect(item.clips?.match_name).toBe('バンカラマッチ');
      expect(item.clips?.video_assets[0].video_id).toBe('recorded/video1.mp4');
    });

    it('item_finish で成功したアイテムの dismissed が true になる', () => {
      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'start',
          items: ['動画A', '動画B'],
          total: 2,
        })
      );

      sm.applyEvent(
        makeEvent({
          task_id: 'auto_edit',
          kind: 'item_finish',
          item_index: 0,
          success: true,
        })
      );

      expect(sm.tasks['auto_edit'].items[0].dismissed).toBe(true);
    });
  });
});
