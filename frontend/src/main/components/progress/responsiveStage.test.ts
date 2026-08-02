import { describe, expect, it } from 'vitest';
import { pickResponsiveStage } from './responsiveStage';
import type { TaskState } from './progressStateMachine';

function makeTask(status: TaskState['status']): TaskState {
  return {
    id: 'task',
    title: 'タスク',
    total: 0,
    completed: 0,
    status,
    items: [],
    activeIndex: null,
    errorMessage: null,
    successMessage: null,
    lastUpdated: 0,
    startedAt: null,
    progressPercent: null,
  };
}

describe('pickResponsiveStage', () => {
  it('アップロード実行中は編集実行中よりアップロードを優先する', () => {
    expect(pickResponsiveStage(makeTask('running'), makeTask('running'), 1)).toBe('uploading');
  });

  it('実行中または失敗した工程がなく待機件数があれば待機を選ぶ', () => {
    expect(pickResponsiveStage(undefined, undefined, 1)).toBe('waiting');
  });

  it('編集成功済みで待機件数があれば待機を選ぶ', () => {
    expect(pickResponsiveStage(makeTask('succeeded'), undefined, 1)).toBe('waiting');
  });

  it.each(['failed', 'succeeded'] as const)(
    'アップロードが %s の場合はアップロードを選ぶ',
    (status) => {
      expect(pickResponsiveStage(undefined, makeTask(status), 0)).toBe('uploading');
    }
  );

  it('編集失敗は待機より編集を優先する', () => {
    expect(pickResponsiveStage(makeTask('failed'), undefined, 1)).toBe('editing');
  });

  it('対象となる状態がなければ編集を選ぶ', () => {
    expect(pickResponsiveStage(undefined, undefined, 0)).toBe('editing');
  });

  it('編集実行中は編集を選ぶ', () => {
    expect(pickResponsiveStage(makeTask('running'), undefined, 0)).toBe('editing');
  });
});
