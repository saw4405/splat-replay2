/**
 * Process API Logic Tests
 *
 * 責務：
 * - プロセス制御 API 関数の動作を検証
 * - エラーハンドリングを確認
 *
 * 分類: logic
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { processApi } from './process.ts';

describe('process API', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // fetch のモックを設定
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ========================================
  // processApi.start()
  // ========================================

  describe('processApi.start', () => {
    it('成功時は正常に完了する', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await expect(processApi.start()).resolves.toBeUndefined();

      expect(fetchMock).toHaveBeenCalledWith('/api/process/start', {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      });
    });

    it('エラーレスポンスでDetailを含む場合はそのメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => 'Process already running',
      });

      await expect(processApi.start()).rejects.toThrow('Process already running');
    });

    it('エラーレスポンスでDetailが無い場合はデフォルトメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => '',
      });

      await expect(processApi.start()).rejects.toThrow('自動処理の開始に失敗しました');
    });

    it('ネットワークエラー時はエラーを投げる', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      await expect(processApi.start()).rejects.toThrow('Network error');
    });

    it('複数回呼び出しても正常に動作する', async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      });

      await expect(processApi.start()).resolves.toBeUndefined();
      await expect(processApi.start()).resolves.toBeUndefined();

      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  // ========================================
  // processApi.startSleep()
  // ========================================

  describe('processApi.startSleep', () => {
    it('成功時は正常に完了する', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await expect(processApi.startSleep()).resolves.toBeUndefined();

      expect(fetchMock).toHaveBeenCalledWith('/api/process/sleep/start', {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      });
    });

    it('エラーレスポンスでDetailを含む場合はそのメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => 'Sleep already scheduled',
      });

      await expect(processApi.startSleep()).rejects.toThrow('Sleep already scheduled');
    });

    it('エラーレスポンスでDetailが無い場合はデフォルトメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => '',
      });

      await expect(processApi.startSleep()).rejects.toThrow('自動スリープの開始に失敗しました');
    });

    it('ネットワークエラー時はエラーを投げる', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      await expect(processApi.startSleep()).rejects.toThrow('Network error');
    });
  });

  // ========================================
  // API 呼び出しエラーハンドリング
  // ========================================

  describe('エラーハンドリング', () => {
    it('HTTP 500 エラーをハンドリングする（start）', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => 'Internal Server Error',
      });

      await expect(processApi.start()).rejects.toThrow('Internal Server Error');
    });

    it('HTTP 500 エラーをハンドリングする（startSleep）', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => 'Internal Server Error',
      });

      await expect(processApi.startSleep()).rejects.toThrow('Internal Server Error');
    });

    it('HTTP 400 エラーをハンドリングする（start）', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        text: async () => 'Bad Request',
      });

      await expect(processApi.start()).rejects.toThrow('Bad Request');
    });

    it('HTTP 400 エラーをハンドリングする（startSleep）', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        text: async () => 'Bad Request',
      });

      await expect(processApi.startSleep()).rejects.toThrow('Bad Request');
    });
  });
});
