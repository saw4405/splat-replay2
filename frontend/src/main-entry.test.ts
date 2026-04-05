import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mountMock = vi.hoisted(() => vi.fn(() => ({ $set: vi.fn(), $on: vi.fn() })));
const flushSyncMock = vi.hoisted(() => vi.fn());

vi.mock('svelte', async () => {
  const actual = await vi.importActual<typeof import('svelte')>('svelte');
  return {
    ...actual,
    mount: mountMock,
    flushSync: flushSyncMock,
  };
});

vi.mock('./App.svelte', () => ({
  default: {},
}));

describe('main entry', () => {
  beforeEach(() => {
    vi.resetModules();
    mountMock.mockClear();
    flushSyncMock.mockClear();
    vi.spyOn(console, 'log').mockImplementation(() => {});
    document.body.innerHTML = '';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  it('mount と flushSync でアプリ初期化を完了する', async () => {
    document.body.innerHTML = '<div id="app"></div>';

    const module = await import('./main');

    expect(mountMock).toHaveBeenCalledTimes(1);
    expect(mountMock.mock.calls[0]?.[1]).toEqual({
      target: document.getElementById('app'),
    });
    expect(flushSyncMock).toHaveBeenCalledTimes(1);
    expect(module.default).toBe(mountMock.mock.results[0]?.value);
  });

  it('mount 対象がなければ明示的に失敗する', async () => {
    await expect(import('./main')).rejects.toThrow('App target element was not found');
    expect(mountMock).not.toHaveBeenCalled();
    expect(flushSyncMock).not.toHaveBeenCalled();
  });
});
