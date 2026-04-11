/**
 * Recording API Logic Tests
 *
 * 責務：
 * - 録画制御 API 関数の動作を検証
 * - エラーハンドリングを確認
 * - レスポンス処理を確認
 *
 * 分類: logic
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getRecorderPreviewMode,
  getRecorderState,
  recoverCaptureDevice,
  startRecorder,
} from './recording.ts';
import type {
  CaptureDeviceRecoveryResponse,
  RecorderPreviewModeResponse,
  RecorderStateResponse,
} from './types.ts';

describe('recording API', () => {
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
  // startRecorder()
  // ========================================

  describe('startRecorder', () => {
    it('成功時は正常に完了する', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await expect(startRecorder()).resolves.toBeUndefined();

      expect(fetchMock).toHaveBeenCalledWith('/api/recorder/start', {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      });
    });

    it('エラーレスポンスでDetailを含む場合はそのメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => 'Recorder already running',
      });

      await expect(startRecorder()).rejects.toThrow('Recorder already running');
    });

    it('エラーレスポンスでDetailが無い場合はデフォルトメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => '',
      });

      await expect(startRecorder()).rejects.toThrow('Failed to start auto recorder');
    });

    it('ネットワークエラー時はエラーを投げる', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      await expect(startRecorder()).rejects.toThrow('Network error');
    });
  });

  // ========================================
  // getRecorderState()
  // ========================================

  describe('getRecorderState', () => {
    it('成功時は状態文字列を返す', async () => {
      const mockResponse: RecorderStateResponse = {
        state: 'recording',
      };

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getRecorderState();

      expect(result).toBe('recording');
      expect(fetchMock).toHaveBeenCalledWith('/api/recorder/state', {
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      });
    });

    it('停止状態を正しく返す', async () => {
      const mockResponse: RecorderStateResponse = {
        state: 'stopped',
      };

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getRecorderState();

      expect(result).toBe('stopped');
    });

    it('エラーレスポンスでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => 'State retrieval failed',
      });

      await expect(getRecorderState()).rejects.toThrow('State retrieval failed');
    });

    it('エラーレスポンスでDetailが無い場合はデフォルトメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => '',
      });

      await expect(getRecorderState()).rejects.toThrow('Failed to fetch recorder state');
    });

    it('不正なJSON形式でエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(getRecorderState()).rejects.toThrow('Invalid JSON');
    });
  });

  // ========================================
  // getRecorderPreviewMode()
  // ========================================

  describe('getRecorderPreviewMode', () => {
    it('成功時はプレビューモードを返す（live_capture）', async () => {
      const mockResponse: RecorderPreviewModeResponse = {
        mode: 'live_capture',
      };

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getRecorderPreviewMode();

      expect(result).toBe('live_capture');
      expect(fetchMock).toHaveBeenCalledWith('/api/recorder/preview-mode', {
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      });
    });

    it('成功時はプレビューモードを返す（video_file）', async () => {
      const mockResponse: RecorderPreviewModeResponse = {
        mode: 'video_file',
      };

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getRecorderPreviewMode();

      expect(result).toBe('video_file');
    });

    it('エラーレスポンスでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => 'Preview mode retrieval failed',
      });

      await expect(getRecorderPreviewMode()).rejects.toThrow('Preview mode retrieval failed');
    });

    it('エラーレスポンスでDetailが無い場合はデフォルトメッセージでエラーを投げる', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => '',
      });

      await expect(getRecorderPreviewMode()).rejects.toThrow(
        'Failed to fetch recorder preview mode'
      );
    });
  });

  describe('recoverCaptureDevice', () => {
    it('復旧 API のレスポンスを返す', async () => {
      const mockResponse: CaptureDeviceRecoveryResponse = {
        attempted: true,
        recovered: false,
        message: 'recover failed',
        action: 'restart-device',
      };

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await recoverCaptureDevice('manual');

      expect(result).toEqual(mockResponse);
      expect(fetchMock).toHaveBeenCalledWith('/api/device/recover', {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ trigger: 'manual' }),
      });
    });

    it('復旧 API が失敗したときは detail を含むエラーを返す', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => 'restart failed',
      });

      await expect(recoverCaptureDevice('manual')).rejects.toThrow('restart failed');
    });
  });
});
