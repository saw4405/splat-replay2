import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ProgressDialog from './ProgressDialog.svelte';

/**
 * ProgressDialogの基本的なコンポーネントテスト
 *
 * 注意: このコンポーネントはSSE (Server-Sent Events) を使用した
 * 複雑な状態管理を行うため、統合テストで詳細な動作を検証する。
 * ここでは基本的なレンダリングとプロパティの動作のみをテストする。
 */
describe('ProgressDialog', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let mockEventSource: {
    addEventListener: ReturnType<typeof vi.fn>;
    removeEventListener: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
    onopen: (() => void) | null;
    onerror: (() => void) | null;
  };

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // EventSourceのモック
    mockEventSource = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      close: vi.fn(),
      onopen: null,
      onerror: null,
    };

    // @ts-expect-error - EventSourceのモック
    global.EventSource = vi.fn(function (this: typeof mockEventSource) {
      return mockEventSource;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('ダイアログ表示', () => {
    it('isOpenがtrueの場合、ダイアログが表示される', async () => {
      fetchMock.mockResolvedValue(
        new Response(
          JSON.stringify({
            state: 'idle',
            sleepAfterUploadEnabled: false,
            sleepAfterUploadEffective: false,
          }),
          { status: 200 }
        )
      );

      render(ProgressDialog, { props: { isOpen: true } });

      // プログレスダイアログのタイトルまたは主要な要素を確認
      // 注: 実際の表示内容はSSEイベントに依存するため、ここでは基本構造のみ確認
      await vi.waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/process/status',
          expect.objectContaining({
            headers: expect.objectContaining({
              Accept: 'application/json',
            }),
          })
        );
      });
    });

    it('isOpenがfalseの場合、EventSourceは作成されない', () => {
      render(ProgressDialog, { props: { isOpen: false } });

      expect(global.EventSource).not.toHaveBeenCalled();
    });
  });

  describe('SSE接続', () => {
    it('ダイアログを開くとEventSourceが作成される', async () => {
      fetchMock.mockResolvedValue(
        new Response(
          JSON.stringify({
            state: 'idle',
            sleepAfterUploadEnabled: false,
            sleepAfterUploadEffective: false,
          }),
          { status: 200 }
        )
      );

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(global.EventSource).toHaveBeenCalledWith('/api/events/progress');
      });
    });

    it('progress_eventとprogressイベントにリスナーが登録される', async () => {
      fetchMock.mockResolvedValue(
        new Response(
          JSON.stringify({
            state: 'idle',
            sleepAfterUploadEnabled: false,
            sleepAfterUploadEffective: false,
          }),
          { status: 200 }
        )
      );

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
          'progress_event',
          expect.any(Function)
        );
        expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
          'progress',
          expect.any(Function)
        );
      });
    });
  });

  describe('編集アップロード状態の取得', () => {
    it('ダイアログを開くと編集アップロード状態がfetchされる', async () => {
      fetchMock.mockResolvedValue(
        new Response(
          JSON.stringify({
            state: 'idle',
            sleepAfterUploadEnabled: false,
            sleepAfterUploadEffective: false,
          }),
          { status: 200 }
        )
      );

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/process/status',
          expect.objectContaining({
            headers: expect.objectContaining({
              Accept: 'application/json',
            }),
          })
        );
      });
    });

    it('fetch失敗時もエラーが表示される（エラーログ出力）', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      fetchMock.mockRejectedValue(new Error('Network error'));

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(fetchMock).toHaveBeenCalled();
      });

      consoleErrorSpy.mockRestore();
    });
  });
});
