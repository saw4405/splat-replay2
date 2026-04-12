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
  UI_COUNTDOWN_TICK_INTERVAL_MS,
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

  it('cpu は gpu より遅いプレビュー更新間隔を使う', () => {
    expect(GPU_PREVIEW_FRAME_POLL_INTERVAL_MS).toBe(500);
    expect(CPU_PREVIEW_FRAME_POLL_INTERVAL_MS).toBe(1200);
    expect(GPU_DEVICE_STATUS_POLL_INTERVAL_MS).toBe(1500);
    expect(CPU_DEVICE_STATUS_POLL_INTERVAL_MS).toBe(2500);
    expect(GPU_PROCESS_STATUS_POLL_INTERVAL_MS).toBe(3000);
    expect(CPU_PROCESS_STATUS_POLL_INTERVAL_MS).toBe(5000);
    expect(CPU_PREVIEW_FRAME_POLL_INTERVAL_MS).toBeGreaterThan(GPU_PREVIEW_FRAME_POLL_INTERVAL_MS);
    expect(getPreviewFramePollIntervalMs('gpu')).toBe(500);
    expect(getPreviewFramePollIntervalMs('cpu')).toBe(1200);
    expect(getDeviceStatusPollIntervalMs('gpu')).toBe(1500);
    expect(getDeviceStatusPollIntervalMs('cpu')).toBe(2500);
    expect(getProcessStatusPollIntervalMs('gpu')).toBe(3000);
    expect(getProcessStatusPollIntervalMs('cpu')).toBe(5000);
    expect(UI_COUNTDOWN_TICK_INTERVAL_MS).toBe(250);
  });
});
