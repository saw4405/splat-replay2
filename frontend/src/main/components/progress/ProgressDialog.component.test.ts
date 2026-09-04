import { cleanup, render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ProgressDialog from './ProgressDialog.svelte';

const imageLoaderHarness = vi.hoisted(() => ({
  requests: new Map<
    string,
    {
      url: string;
      ownerId: string;
      slotId: string;
      onReady: (image: { sourceUrl: string; objectUrl: string }) => void;
      onError: (error: Error) => void;
    }
  >(),
  releaseSlot: vi.fn(),
  releaseOwner: vi.fn(),
  clear: vi.fn(),
  dispose: vi.fn(),
}));

vi.mock('./progressImageLoader', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./progressImageLoader')>();
  return {
    ...actual,
    ProgressImageLoader: class {
      request(request: {
        url: string;
        ownerId: string;
        slotId: string;
        onReady: (image: { sourceUrl: string; objectUrl: string }) => void;
        onError: (error: Error) => void;
      }): void {
        imageLoaderHarness.requests.set(`${request.ownerId}\u0000${request.slotId}`, request);
      }

      releaseSlot(ownerId: string, slotId: string): void {
        imageLoaderHarness.requests.delete(`${ownerId}\u0000${slotId}`);
        imageLoaderHarness.releaseSlot(ownerId, slotId);
      }

      releaseOwner(ownerId: string): void {
        imageLoaderHarness.releaseOwner(ownerId);
      }

      clear(): void {
        imageLoaderHarness.requests.clear();
        imageLoaderHarness.clear();
      }

      dispose(): void {
        imageLoaderHarness.requests.clear();
        imageLoaderHarness.dispose();
      }
    },
  };
});

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
    imageLoaderHarness.requests.clear();
    imageLoaderHarness.releaseSlot.mockClear();
    imageLoaderHarness.releaseOwner.mockClear();
    imageLoaderHarness.clear.mockClear();
    imageLoaderHarness.dispose.mockClear();
    fetchMock = vi.fn();
    global.fetch = fetchMock;
    if (!Element.prototype.getAnimations) {
      Object.defineProperty(Element.prototype, 'getAnimations', {
        configurable: true,
        value: vi.fn(() => []),
      });
    }

    // EventSourceのモック
    mockEventSource = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      close: vi.fn(),
      onopen: null,
      onerror: null,
    };

    const eventSourceMockConstructor = vi.fn(function (this: typeof mockEventSource) {
      return mockEventSource;
    });
    vi.stubGlobal('EventSource', eventSourceMockConstructor);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function mockIdleStatusResponse(): void {
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
  }

  function registeredEventHandler(name: string): ((event: MessageEvent) => void) | undefined {
    return mockEventSource.addEventListener.mock.calls.find(
      ([eventName]) => eventName === name
    )?.[1];
  }

  function emitProgressEvent(payload: Record<string, unknown>): void {
    registeredEventHandler('progress_event')?.(
      new MessageEvent('progress_event', {
        data: JSON.stringify({
          task_id: 'auto_edit',
          kind: 'start',
          task_name: '自動編集',
          total: null,
          completed: null,
          stage_key: null,
          stage_label: null,
          stage_index: null,
          stage_count: null,
          success: null,
          message: null,
          items: null,
          item_index: null,
          item_key: null,
          item_label: null,
          progress_percent: null,
          clips: null,
          ...payload,
        }),
      })
    );
  }

  async function notifyImageReady(
    ownerId: string,
    slotId: string,
    objectUrl: string
  ): Promise<void> {
    const key = `${ownerId}\u0000${slotId}`;
    await vi.waitFor(() => {
      expect(imageLoaderHarness.requests.has(key)).toBe(true);
    });
    const request = imageLoaderHarness.requests.get(key);
    request?.onReady({ sourceUrl: request.url, objectUrl });
  }

  async function notifyImageError(ownerId: string, slotId: string): Promise<void> {
    const key = `${ownerId}\u0000${slotId}`;
    await vi.waitFor(() => {
      expect(imageLoaderHarness.requests.has(key)).toBe(true);
    });
    imageLoaderHarness.requests.get(key)?.onError(new Error('image failed'));
  }

  function videoAsset(videoId: string) {
    return {
      video_id: videoId,
      duration_seconds: 240,
      judgement: 'WIN',
      stage_name: 'SCORCH_GORGE',
      kill: 5,
      death: 2,
      special: 3,
      gold_medals: 1,
      silver_medals: 2,
      rate: null,
    };
  }

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

    it('編集エリアと待機エリアの状態アイコンが表示される', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(screen.getByRole('img', { name: '編集中エリア' })).toBeVisible();
        expect(screen.getByRole('img', { name: '待機中エリア' })).toBeVisible();
      });
    });
  });

  describe('SSE接続', () => {
    it('ダイアログを開くとEventSourceが作成される', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(global.EventSource).toHaveBeenCalledWith('/api/events/progress');
      });
    });

    it('progress_eventとprogressイベントにリスナーが登録される', async () => {
      mockIdleStatusResponse();

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

    it('自動編集タスク開始時に番号付きエリアタイトルが表示される', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画'],
            item_index: null,
            item_key: null,
            item_label: null,
          }),
        })
      );

      await vi.waitFor(() => {
        const editingRegion = screen.getByRole('region', { name: '1. 編集' });

        expect(screen.getByRole('heading', { name: '1. 編集' })).toBeVisible();
        expect(screen.getByRole('heading', { name: '2. 待機' })).toBeVisible();
        expect(screen.getByRole('heading', { name: '3. アップロード' })).toBeVisible();
        expect(editingRegion).toBeVisible();
        expect(editingRegion).toHaveAttribute('aria-current', 'step');
        expect(screen.getByRole('region', { name: '2. 待機' })).not.toHaveAttribute('aria-current');
        expect(screen.getByRole('region', { name: '3. アップロード' })).not.toHaveAttribute(
          'aria-current'
        );
      });
    });
    it.each([
      ['成功', true, null, 'status', 'アップロード完了', '自動アップロードが完了しました。'],
      [
        '失敗',
        false,
        'アップロードAPIエラー',
        'alert',
        'アップロード失敗',
        'アップロードAPIエラー',
      ],
    ] as const)(
      '編集継続中でもアップロード%s後はterminal詳細を表示する',
      async (_caseLabel, success, message, role, accessibleName, expectedMessage) => {
        mockIdleStatusResponse();

        render(ProgressDialog, { props: { isOpen: true } });

        await vi.waitFor(() => {
          expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
        });

        emitProgressEvent({
          task_id: 'auto_edit',
          kind: 'start',
          task_name: '自動編集',
          total: 1,
          completed: 0,
        });
        emitProgressEvent({
          task_id: 'auto_upload',
          kind: 'start',
          task_name: '自動アップロード',
          total: 1,
          completed: 0,
        });
        emitProgressEvent({
          task_id: 'auto_upload',
          kind: 'finish',
          task_name: '自動アップロード',
          total: 1,
          completed: 1,
          success,
          message,
        });

        await vi.waitFor(() => {
          expect(screen.getByRole('region', { name: '3. アップロード' })).toHaveAttribute(
            'aria-current',
            'step'
          );
          expect(
            screen.getByRole('region', { name: 'YouTubeアップロードエリア 展開中' })
          ).toBeVisible();
          expect(screen.getByRole(role, { name: accessibleName })).toHaveTextContent(
            expectedMessage
          );
          expect(
            screen.queryByRole('progressbar', { name: 'YouTube再構成進捗' })
          ).not.toBeInTheDocument();
        });
      }
    );

    it('デコード成功通知前はメイン画像を切り替えず通知後にObject URLを表示する', async () => {
      mockIdleStatusResponse();
      render(ProgressDialog, { props: { isOpen: true } });
      emitProgressEvent({
        kind: 'start',
        total: 1,
        completed: 0,
        items: ['テスト動画'],
        clips: [
          {
            group_index: 0,
            date_label: '06/27\n00:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチエリア',
            video_assets: [
              {
                video_id: 'recorded/sample.mkv',
                duration_seconds: 240,
                judgement: 'WIN',
                stage_name: 'SCORCH_GORGE',
                kill: 5,
                death: 2,
                special: 3,
                gold_medals: 1,
                silver_medals: 2,
                rate: null,
              },
            ],
          },
        ],
      });
      emitProgressEvent({
        kind: 'item_stage',
        total: 1,
        completed: 0,
        message: '結合中',
        item_index: 0,
        item_key: 'concat',
        item_label: '動画結合',
        progress_percent: 25,
      });

      await vi.waitFor(() => {
        expect(imageLoaderHarness.requests.has('progress-dialog\u0000main-live')).toBe(true);
      });
      expect(screen.queryByTestId('progress-main-image')).not.toBeInTheDocument();

      const request = imageLoaderHarness.requests.get('progress-dialog\u0000main-live');
      request?.onReady({ sourceUrl: request.url, objectUrl: 'blob:main-ready' });

      await vi.waitFor(() => {
        expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:main-ready');
      });
    });

    it('新しいメイン画像の取得中と最終失敗後も最後の成功画像を維持する', async () => {
      mockIdleStatusResponse();
      render(ProgressDialog, { props: { isOpen: true } });
      emitProgressEvent({
        kind: 'start',
        total: 1,
        completed: 0,
        items: ['active'],
        clips: [
          {
            group_index: 0,
            date_label: '06/27\n00:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチエリア',
            video_assets: [videoAsset('recorded/main.mkv')],
          },
        ],
      });
      emitProgressEvent({
        kind: 'item_stage',
        total: 1,
        completed: 0,
        item_index: 0,
        item_key: 'concat',
        item_label: '動画結合',
        progress_percent: 25,
      });

      await notifyImageReady('progress-dialog', 'main-live', 'blob:live-0');
      const previousRequest = imageLoaderHarness.requests.get('progress-dialog\u0000main-live');
      expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:live-0');

      emitProgressEvent({
        kind: 'item_stage',
        total: 1,
        completed: 0,
        item_index: 0,
        item_key: 'concat',
        item_label: '動画結合',
        progress_percent: 50,
      });
      await vi.waitFor(() => {
        expect(imageLoaderHarness.requests.get('progress-dialog\u0000main-live')?.url).not.toBe(
          previousRequest?.url
        );
      });
      expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:live-0');

      await notifyImageError('progress-dialog', 'main-live');
      expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:live-0');
    });

    it('シークバー画像の失敗は他の成功画像を消さない', async () => {
      mockIdleStatusResponse();
      render(ProgressDialog, { props: { isOpen: true } });
      emitProgressEvent({
        kind: 'start',
        total: 1,
        completed: 0,
        items: ['active'],
        clips: [
          {
            group_index: 0,
            date_label: '06/27\n00:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチエリア',
            video_assets: [videoAsset('recorded/clip-a.mkv'), videoAsset('recorded/clip-b.mkv')],
          },
        ],
      });
      emitProgressEvent({
        kind: 'item_stage',
        total: 1,
        completed: 0,
        item_index: 0,
        item_key: 'concat',
        item_label: '動画結合',
        progress_percent: 0,
      });

      await notifyImageReady('progress-dialog', 'main-live', 'blob:main');
      const ownerId = 'edit-item:recorded/clip-a.mkv';
      await notifyImageReady(ownerId, 'clip:0:recorded/clip-a.mkv', 'blob:clip-0');
      await notifyImageError(ownerId, 'clip:1:recorded/clip-b.mkv');

      await vi.waitFor(() => {
        expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:main');
        expect(screen.getAllByAltText('thumb unmerged fg')).toHaveLength(1);
        expect(screen.getByAltText('thumb unmerged fg')).toHaveAttribute('src', 'blob:clip-0');
      });
    });

    it('項目完了とダイアログ終了で画像slotを解放する', async () => {
      mockIdleStatusResponse();
      const { rerender, unmount } = render(ProgressDialog, { props: { isOpen: true } });
      emitProgressEvent({
        kind: 'start',
        total: 1,
        completed: 0,
        items: ['active'],
        clips: [
          {
            group_index: 0,
            date_label: '06/27\n00:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチエリア',
            video_assets: [videoAsset('recorded/release.mkv')],
          },
        ],
      });
      emitProgressEvent({
        kind: 'item_stage',
        total: 1,
        completed: 0,
        item_index: 0,
        item_key: 'concat',
        item_label: '動画結合',
        progress_percent: 0,
      });
      await vi.waitFor(() => {
        expect(
          imageLoaderHarness.requests.has(
            'edit-item:recorded/release.mkv\u0000clip:0:recorded/release.mkv'
          )
        ).toBe(true);
      });

      emitProgressEvent({
        kind: 'item_finish',
        total: 1,
        completed: 1,
        item_index: 0,
        success: true,
      });
      await vi.waitFor(() => {
        expect(imageLoaderHarness.releaseSlot).toHaveBeenCalledWith(
          'edit-item:recorded/release.mkv',
          'clip:0:recorded/release.mkv'
        );
      });

      imageLoaderHarness.clear.mockClear();
      await rerender({ isOpen: false });
      await vi.waitFor(() => {
        expect(imageLoaderHarness.clear).toHaveBeenCalledTimes(1);
      });
      unmount();
      expect(imageLoaderHarness.dispose).toHaveBeenCalledTimes(1);
    });

    it('次のタイムスケジュールの結合開始時は再生ヘッドが前回の右端位置を引き継がない', async () => {
      mockIdleStatusResponse();

      const { container } = render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 2,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['1つ目のスケジュール', '2つ目のスケジュール'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27\n00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチエリア',
                video_assets: [
                  {
                    video_id: 'recorded/first.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'SCORCH_GORGE',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
              {
                group_index: 1,
                date_label: '06/27\n02:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチヤグラ',
                video_assets: [
                  {
                    video_id: 'recorded/second.mkv',
                    duration_seconds: 240,
                    judgement: 'LOSE',
                    stage_name: 'MAKO_MART',
                    kill: 3,
                    death: 4,
                    special: 2,
                    gold_medals: 0,
                    silver_medals: 1,
                    rate: null,
                  },
                ],
              },
            ],
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 2,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '1本目を結合中',
            items: null,
            item_index: 0,
            item_key: 'concat',
            item_label: '動画結合',
            progress_percent: 100,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(container.querySelector('.timeline-row.active .timeline-playhead')).toHaveStyle(
          'left: 100%;'
        );
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_finish',
            task_name: '自動編集',
            total: 2,
            completed: 1,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: true,
            message: null,
            items: null,
            item_index: 0,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: null,
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 2,
            completed: 1,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '2本目を結合中',
            items: null,
            item_index: 1,
            item_key: 'concat',
            item_label: '動画結合',
            progress_percent: 1,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        const activePlayhead = container.querySelector('.timeline-row.active .timeline-playhead');
        expect(activePlayhead).toHaveStyle('left: 1%;');
        expect(activePlayhead).not.toHaveStyle('left: 100%;');
      });
    });

    it('最後の編集アイテム完了後も動画枠に直前のプレビューを残す', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27\n00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチエリア',
                video_assets: [
                  {
                    video_id: 'recorded/sample.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'SCORCH_GORGE',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
            ],
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '結合中',
            items: null,
            item_index: 0,
            item_key: 'concat',
            item_label: '動画結合',
            progress_percent: 100,
            clips: null,
          }),
        })
      );

      const expected = 'blob:last-game-frame';
      await notifyImageReady('progress-dialog', 'main-live', expected);
      await vi.waitFor(() => {
        expect(
          screen
            .getAllByAltText('Preview Frame')
            .some((img) => img.getAttribute('src') === expected)
        ).toBe(true);
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_finish',
            task_name: '自動編集',
            total: 1,
            completed: 1,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: true,
            message: null,
            items: null,
            item_index: 0,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(
          screen
            .getAllByAltText('Preview Frame')
            .some((img) => img.getAttribute('src') === expected)
        ).toBe(true);
        expect(screen.queryByText('動画結合を開始します...')).not.toBeInTheDocument();
      });
    });

    it('サムネイル埋め込み中は完成サムネイルを左上から1行ずつ表示する', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27 00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチエリア',
                video_assets: [
                  {
                    video_id: 'recorded/sample.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'SCORCH_GORGE',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
            ],
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: 'メタデータ・サムネイルを埋め込み中',
            items: null,
            item_index: 0,
            item_key: 'thumbnail',
            item_label: 'サムネイル編集',
            progress_percent: 50.1,
            clips: null,
          }),
        })
      );

      await notifyImageReady('progress-dialog', 'main-final', 'blob:final-reveal');
      const finalThumbnail = await screen.findByAltText('Final Thumbnail');
      expect(finalThumbnail).toHaveAttribute('src', 'blob:final-reveal');
      const revealStyle = finalThumbnail.parentElement?.getAttribute('style') ?? '';
      expect(revealStyle).toContain('--pixel-reveal-progress: 0.501');
      expect(revealStyle).toContain('--pixel-reveal-complete-height: 270px');
      expect(revealStyle).toContain('--pixel-reveal-current-row-top: 270px');
      expect(revealStyle).toContain('--pixel-reveal-current-width: 518px');
      expect(revealStyle).toContain('--pixel-reveal-row-height: 1px');
      expect(revealStyle).not.toContain('--final-blur');
      expect(screen.queryByText('メタデータ・サムネイルを埋め込み中')).not.toBeInTheDocument();

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: 'メタデータ・サムネイルを埋め込み中',
            items: null,
            item_index: 0,
            item_key: 'thumbnail',
            item_label: 'サムネイル編集',
            progress_percent: 100,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(finalThumbnail.parentElement?.getAttribute('style')).toContain(
          '--pixel-reveal-progress: 1.000'
        );
        expect(finalThumbnail.parentElement?.getAttribute('style')).toContain(
          '--pixel-reveal-complete-height: 540px'
        );
        expect(finalThumbnail.parentElement).toHaveClass('final-settled');
      });
    });

    it('サムネイル生成中は未生成の完成サムネイルURLを読みに行かない', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27\n00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチエリア',
                video_assets: [
                  {
                    video_id: 'recorded/sample.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'SCORCH_GORGE',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
            ],
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '結合中',
            items: null,
            item_index: 0,
            item_key: 'concat',
            item_label: '動画結合',
            progress_percent: 100,
            clips: null,
          }),
        })
      );

      await notifyImageReady('progress-dialog', 'main-live', 'blob:live-before-thumbnail');

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: 'サムネイル画像を生成中',
            items: null,
            item_index: 0,
            item_key: 'thumbnail',
            item_label: 'サムネイル編集',
            progress_percent: null,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(screen.queryByAltText('Final Thumbnail')).not.toBeInTheDocument();
        expect(
          screen
            .getAllByAltText('Preview Frame')
            .some((img) => img.getAttribute('src') === 'blob:live-before-thumbnail')
        ).toBe(true);
      });
    });

    it('完成サムネイルの成功時だけ差し替え失敗時は最後のゲームフレームを維持する', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 2,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画', '次の動画'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27 00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチエリア',
                thumbnail_filename: '20260627_00_Xマッチ_ガチエリア.png',
                video_assets: [
                  {
                    video_id: 'recorded/sample.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'SCORCH_GORGE',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
              {
                group_index: 1,
                date_label: '06/27 01:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチエリア',
                thumbnail_filename: '20260627_01_Xマッチ_ガチエリア.png',
                video_assets: [videoAsset('recorded/next.mkv')],
              },
            ],
          }),
        })
      );

      await notifyImageReady('progress-dialog', 'main-live', 'blob:live-fallback');

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: 'メタデータ・サムネイルを埋め込み中',
            items: null,
            item_index: 0,
            item_key: 'thumbnail',
            item_label: 'サムネイル編集',
            progress_percent: 50,
            clips: null,
          }),
        })
      );

      const failedFinalUrl = imageLoaderHarness.requests.get(
        'progress-dialog\u0000main-final'
      )?.url;
      await notifyImageError('progress-dialog', 'main-final');
      await vi.waitFor(() => {
        expect(screen.getByTestId('progress-main-image')).toHaveAttribute(
          'src',
          'blob:live-fallback'
        );
      });

      emitProgressEvent({
        kind: 'item_stage',
        total: 2,
        completed: 0,
        item_index: 0,
        item_key: 'save',
        item_label: '保存・整理',
        message: '保存中',
      });
      emitProgressEvent({
        kind: 'advance',
        total: 2,
        completed: 1,
      });
      const completedOwnerId = 'completed:recorded/sample.mkv';
      await notifyImageReady(completedOwnerId, 'fallback', 'blob:completed-fallback');
      await notifyImageError(completedOwnerId, 'final-thumbnail');
      await vi.waitFor(() => {
        expect(screen.getByAltText('thumb')).toHaveAttribute('src', 'blob:completed-fallback');
      });

      emitProgressEvent({
        kind: 'item_stage',
        total: 2,
        completed: 1,
        item_index: 1,
        item_key: 'thumbnail',
        item_label: 'サムネイル編集',
        message: 'メタデータ・サムネイルを埋め込み中',
        progress_percent: 50,
      });
      await vi.waitFor(() => {
        expect(imageLoaderHarness.requests.get('progress-dialog\u0000main-final')?.url).not.toBe(
          failedFinalUrl
        );
      });
      await notifyImageReady('progress-dialog', 'main-final', 'blob:next-final');
      await vi.waitFor(() => {
        expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:next-final');
      });
    });

    it('タイムスケジュールの編集完了後に動画枠の完成サムネイルをアップロード待機エリアへ移動する', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27 00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチヤグラ',
                thumbnail_filename: '20260627_00_Xマッチ_ガチヤグラ.png',
                video_assets: [
                  {
                    video_id: 'recorded/sample.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'AMABI_ART_UNIVERSITY',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
            ],
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: 'メタデータ・サムネイルを埋め込み中',
            items: null,
            item_index: 0,
            item_key: 'thumbnail',
            item_label: 'サムネイル編集',
            progress_percent: 100,
            clips: null,
          }),
        })
      );

      await notifyImageReady('progress-dialog', 'main-final', 'blob:final-main');
      const finalThumbnail = await screen.findByAltText('Final Thumbnail');
      expect(finalThumbnail).toHaveAttribute('src', 'blob:final-main');

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '【ガチヤグラ】海女美術大学の軌跡',
            items: null,
            item_index: 0,
            item_key: 'save',
            item_label: '保存・整理',
            progress_percent: null,
            clips: null,
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'advance',
            task_name: '自動編集',
            total: 1,
            completed: 1,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: null,
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: null,
          }),
        })
      );

      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'finish',
        total: 1,
        completed: 1,
        success: true,
      });

      await notifyImageReady(
        'completed:recorded/sample.mkv',
        'final-thumbnail',
        'blob:final-completed-card'
      );

      await vi.waitFor(() => {
        expect(screen.getByText('【ガチヤグラ】海女美術大学の軌跡')).toBeVisible();
        expect(
          screen.queryByText('【ガチヤグラ】AMABI_ART_UNIVERSITYの軌跡')
        ).not.toBeInTheDocument();
        expect(screen.getByText('編集完了・アップロード待ち')).toBeVisible();
        expect(screen.getByAltText('thumb')).toHaveAttribute('src', 'blob:final-completed-card');

        const waitingRegion = screen.getByRole('region', { name: '2. 待機' });
        expect(waitingRegion).toBeVisible();
        expect(waitingRegion).toHaveAttribute('aria-current', 'step');
        expect(screen.getByRole('region', { name: '1. 編集' })).not.toHaveAttribute('aria-current');
        expect(screen.getByRole('region', { name: '3. アップロード' })).not.toHaveAttribute(
          'aria-current'
        );
      });
    });

    it('全編集完了後に待機エリア右側のYouTubeエリアを拡げ、アップロード進捗を再構成ブロックで表す', async () => {
      mockIdleStatusResponse();

      const { container } = render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      expect(
        screen.getByRole('region', { name: 'YouTubeアップロードエリア 待機中' })
      ).toBeVisible();

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'start',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['テスト動画'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: [
              {
                group_index: 0,
                date_label: '06/27 00:00～',
                match_name: 'Xマッチ',
                rule_name: 'ガチヤグラ',
                thumbnail_filename: '20260627_00_Xマッチ_ガチヤグラ.png',
                video_assets: [
                  {
                    video_id: 'recorded/sample.mkv',
                    duration_seconds: 240,
                    judgement: 'WIN',
                    stage_name: 'AMABI_ART_UNIVERSITY',
                    kill: 5,
                    death: 2,
                    special: 3,
                    gold_medals: 1,
                    silver_medals: 2,
                    rate: null,
                  },
                ],
              },
            ],
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'item_stage',
            task_name: '自動編集',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '【ガチヤグラ】海女美術大学の軌跡',
            items: null,
            item_index: 0,
            item_key: 'save',
            item_label: '保存・整理',
            progress_percent: null,
            clips: null,
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'advance',
            task_name: '自動編集',
            total: 1,
            completed: 1,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: null,
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: null,
          }),
        })
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_edit',
            kind: 'finish',
            task_name: '自動編集',
            total: 1,
            completed: 1,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: true,
            message: null,
            items: null,
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: null,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(
          screen.getByRole('region', { name: 'YouTubeアップロードエリア 展開中' })
        ).toBeVisible();
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_upload',
            kind: 'start',
            task_name: '自動アップロード',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: null,
            items: ['【ガチヤグラ】海女美術大学の軌跡'],
            item_index: null,
            item_key: null,
            item_label: null,
            progress_percent: 42,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        const uploadRegion = screen.getByRole('region', { name: '3. アップロード' });
        expect(uploadRegion).toBeVisible();
        expect(uploadRegion).toHaveAttribute('aria-current', 'step');
        expect(screen.getByRole('region', { name: '1. 編集' })).not.toHaveAttribute('aria-current');
        expect(screen.getByRole('region', { name: '2. 待機' })).not.toHaveAttribute('aria-current');

        expect(screen.getByLabelText('YouTube側で再構成中のサムネイル')).toBeVisible();
        expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
          'aria-valuenow',
          '0'
        );
        expect(
          screen.queryByRole('img', { name: 'YouTubeへ飛行中のサムネイルブロック' })
        ).not.toBeInTheDocument();
      });

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_upload',
            kind: 'item_stage',
            task_name: '自動アップロード',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '【ガチヤグラ】海女美術大学の軌跡',
            items: null,
            item_index: 0,
            item_key: 'upload',
            item_label: '動画アップロード',
            progress_percent: 42,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(
          screen.getByRole('img', { name: 'YouTubeへ飛行中のサムネイルブロック' })
        ).toBeVisible();
        expect(screen.getAllByTestId('flying-upload-tile')).toHaveLength(1);
        expect(container.querySelectorAll('.source-tile.transferred')).toHaveLength(1);
        expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
          'aria-valuenow',
          '0'
        );
      });

      await new Promise<void>((resolve) => setTimeout(resolve, 180));
      expect(screen.getAllByTestId('flying-upload-tile')).toHaveLength(1);
      expect(container.querySelectorAll('.source-tile.transferred')).toHaveLength(1);
      expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
        'aria-valuenow',
        '0'
      );

      await vi.waitFor(
        () => {
          expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
            'aria-valuenow',
            '1'
          );
          expect(container.querySelectorAll('.receiver-tile.received')).toHaveLength(1);
        },
        { timeout: 2000 }
      );

      expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
        'aria-valuenow',
        '1'
      );

      registeredEventHandler('progress_event')?.(
        new MessageEvent('progress_event', {
          data: JSON.stringify({
            task_id: 'auto_upload',
            kind: 'item_stage',
            task_name: '自動アップロード',
            total: 1,
            completed: 0,
            stage_key: null,
            stage_label: null,
            stage_index: null,
            stage_count: null,
            success: null,
            message: '【ガチヤグラ】海女美術大学の軌跡',
            items: null,
            item_index: 0,
            item_key: 'upload',
            item_label: '動画アップロード',
            progress_percent: 43,
            clips: null,
          }),
        })
      );

      await vi.waitFor(() => {
        expect(screen.getAllByTestId('flying-upload-tile').length).toBeGreaterThanOrEqual(1);
        expect(container.querySelectorAll('.source-tile.transferred')).toHaveLength(2);
        expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
          'aria-valuenow',
          '1'
        );
      });

      await vi.waitFor(
        () => {
          expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
            'aria-valuenow',
            '2'
          );
          expect(container.querySelectorAll('.receiver-tile.received')).toHaveLength(2);
        },
        { timeout: 2000 }
      );
    });

    it('アップロード完了動画を待機エリアから消し、次の動画の再構成を0%から始める', async () => {
      mockIdleStatusResponse();

      render(ProgressDialog, { props: { isOpen: true } });

      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });

      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'start',
        total: 2,
        completed: 0,
        items: ['動画A', '動画B'],
        clips: [
          {
            group_index: 0,
            date_label: '06/27 00:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチヤグラ',
            thumbnail_filename: 'video-a.png',
            video_assets: [
              {
                video_id: 'recorded/video-a.mkv',
                duration_seconds: 120,
                judgement: 'WIN',
                stage_name: 'AMABI_ART_UNIVERSITY',
                kill: 5,
                death: 2,
                special: 1,
                gold_medals: 1,
                silver_medals: 0,
                rate: null,
              },
            ],
          },
          {
            group_index: 1,
            date_label: '06/27 01:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチヤグラ',
            thumbnail_filename: 'video-b.png',
            video_assets: [
              {
                video_id: 'recorded/video-b.mkv',
                duration_seconds: 120,
                judgement: 'LOSE',
                stage_name: 'MAKO_MART',
                kill: 3,
                death: 4,
                special: 2,
                gold_medals: 0,
                silver_medals: 1,
                rate: null,
              },
            ],
          },
        ],
      });

      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'item_stage',
        total: 2,
        completed: 0,
        item_index: 0,
        item_key: 'save',
        item_label: '保存・整理',
        message: '動画A',
      });
      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'advance',
        total: 2,
        completed: 1,
      });
      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'item_stage',
        total: 2,
        completed: 1,
        item_index: 1,
        item_key: 'save',
        item_label: '保存・整理',
        message: '動画B',
      });
      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'advance',
        total: 2,
        completed: 2,
      });
      emitProgressEvent({
        task_id: 'auto_edit',
        kind: 'finish',
        total: 2,
        completed: 2,
        success: true,
      });

      await vi.waitFor(() => {
        expect(screen.getByText('動画A')).toBeVisible();
        expect(screen.getByText('動画B')).toBeVisible();
      });

      emitProgressEvent({
        task_id: 'auto_upload',
        kind: 'start',
        task_name: '自動アップロード',
        total: 2,
        completed: 0,
        items: ['動画A', '動画B'],
      });
      emitProgressEvent({
        task_id: 'auto_upload',
        kind: 'item_stage',
        task_name: '自動アップロード',
        total: 2,
        completed: 0,
        item_index: 0,
        item_key: 'upload',
        item_label: '動画アップロード',
        message: '動画A',
        progress_percent: 10,
      });

      await vi.waitFor(() => {
        expect(
          screen.getByRole('img', { name: 'YouTubeへ飛行中のサムネイルブロック' })
        ).toBeVisible();
        expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
          'aria-valuenow',
          '0'
        );
      });

      emitProgressEvent({
        task_id: 'auto_upload',
        kind: 'advance',
        task_name: '自動アップロード',
        total: 2,
        completed: 1,
      });

      await vi.waitFor(() => {
        expect(screen.queryByText('動画A')).not.toBeInTheDocument();
        expect(screen.getByText('動画B')).toBeVisible();
        expect(screen.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toHaveAttribute(
          'aria-valuenow',
          '0'
        );
      });
    });
  });

  describe('編集アップロード状態の取得', () => {
    it('ダイアログを開くと編集アップロード状態がfetchされる', async () => {
      mockIdleStatusResponse();

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

    it('実行中はキャンセル要求をDELETEで送信する', async () => {
      fetchMock
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              state: 'idle',
              sleep_after_upload_default: false,
              sleep_after_upload_effective: false,
              sleep_after_upload_overridden: false,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              state: 'cancelling',
              error: null,
              sleep_after_upload_default: false,
              sleep_after_upload_effective: false,
              sleep_after_upload_overridden: false,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        );

      render(ProgressDialog, { props: { isOpen: true } });
      await vi.waitFor(() => {
        expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
      });
      emitProgressEvent({ kind: 'start', total: 1, completed: 0 });

      const cancelButton = await screen.findByRole('button', { name: '編集をキャンセル' });
      cancelButton.click();

      await vi.waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/process/edit-upload',
          expect.objectContaining({ method: 'DELETE' })
        );
      });
      expect(await screen.findByRole('button', { name: '中断中...' })).toBeDisabled();
      expect(screen.getByText('進捗')).toBeInTheDocument();
    });
  });
});
