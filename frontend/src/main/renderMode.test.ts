import { get } from 'svelte/store';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SettingsResponse } from './components/settings/types';
import {
  CPU_DEVICE_STATUS_POLL_INTERVAL_MS,
  CPU_PREVIEW_FRAME_POLL_INTERVAL_MS,
  CPU_PROCESS_STATUS_POLL_INTERVAL_MS,
  GPU_DEVICE_STATUS_POLL_INTERVAL_MS,
  GPU_PREVIEW_FRAME_POLL_INTERVAL_MS,
  GPU_PROCESS_STATUS_POLL_INTERVAL_MS,
  getPreviewFramePollIntervalMs,
  getDeviceStatusPollIntervalMs,
  getProcessStatusPollIntervalMs,
  initializeRenderMode,
  normalizeRenderMode,
  renderMode,
  resetRenderModeForTest,
  resolveRenderModeFromSettingsResponse,
  setRenderMode,
} from './renderMode';

describe('renderMode runtime', () => {
  afterEach(() => {
    resetRenderModeForTest(document);
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('未知の値を gpu に正規化する', () => {
    expect(normalizeRenderMode('gpu')).toBe('gpu');
    expect(normalizeRenderMode('GPU')).toBe('gpu');
    expect(normalizeRenderMode('CPU')).toBe('cpu');
    expect(normalizeRenderMode('broken')).toBe('gpu');
  });

  it('settings レスポンスから render_mode を解決する', () => {
    const response: SettingsResponse = {
      sections: [
        {
          id: 'webview',
          label: '表示',
          fields: [
            {
              id: 'render_mode',
              label: '描画モード',
              description: '',
              type: 'select',
              recommended: false,
              value: 'gpu',
            },
          ],
        },
      ],
    };

    expect(resolveRenderModeFromSettingsResponse(response)).toBe('gpu');
  });

  it('UI grouping 済みの settings レスポンスから render_mode を解決する', () => {
    const response: SettingsResponse = {
      sections: [
        {
          id: 'display',
          label: '表示',
          fields: [
            {
              id: 'render_mode',
              label: '描画モード',
              description: '',
              type: 'select',
              recommended: false,
              value: 'cpu',
            },
          ],
        },
      ],
    };

    expect(resolveRenderModeFromSettingsResponse(response)).toBe('cpu');
  });

  it('setRenderMode が store と document dataset を更新する', () => {
    setRenderMode('cpu', document);

    expect(get(renderMode)).toBe('cpu');
    expect(document.documentElement.dataset.renderMode).toBe('cpu');
  });

  it('initializeRenderMode は fetch 失敗時に gpu へフォールバックする', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    await initializeRenderMode(document);

    expect(get(renderMode)).toBe('gpu');
    expect(document.documentElement.dataset.renderMode).toBe('gpu');
  });

  it('initializeRenderMode は軽量な render mode endpoint を利用する', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ render_mode: 'cpu' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await initializeRenderMode(document);

    expect(fetchMock).toHaveBeenCalledWith('/api/settings/webview-render-mode', {
      cache: 'no-store',
    });
    expect(get(renderMode)).toBe('cpu');
    expect(document.documentElement.dataset.renderMode).toBe('cpu');
  });

  it('cpu は gpu より遅いポーリング間隔を使う', () => {
    // 関係性の検証（CPU は GPU より遅い間隔）
    expect(CPU_PREVIEW_FRAME_POLL_INTERVAL_MS).toBeGreaterThan(GPU_PREVIEW_FRAME_POLL_INTERVAL_MS);
    expect(CPU_DEVICE_STATUS_POLL_INTERVAL_MS).toBeGreaterThan(GPU_DEVICE_STATUS_POLL_INTERVAL_MS);
    expect(CPU_PROCESS_STATUS_POLL_INTERVAL_MS).toBeGreaterThan(
      GPU_PROCESS_STATUS_POLL_INTERVAL_MS
    );

    // getter 関数がモードに応じて正しい定数を返す
    expect(getPreviewFramePollIntervalMs('gpu')).toBe(GPU_PREVIEW_FRAME_POLL_INTERVAL_MS);
    expect(getPreviewFramePollIntervalMs('cpu')).toBe(CPU_PREVIEW_FRAME_POLL_INTERVAL_MS);
    expect(getDeviceStatusPollIntervalMs('gpu')).toBe(GPU_DEVICE_STATUS_POLL_INTERVAL_MS);
    expect(getDeviceStatusPollIntervalMs('cpu')).toBe(CPU_DEVICE_STATUS_POLL_INTERVAL_MS);
    expect(getProcessStatusPollIntervalMs('gpu')).toBe(GPU_PROCESS_STATUS_POLL_INTERVAL_MS);
    expect(getProcessStatusPollIntervalMs('cpu')).toBe(CPU_PROCESS_STATUS_POLL_INTERVAL_MS);
  });
});
