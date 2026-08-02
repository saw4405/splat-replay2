import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ProgressDialog from './ProgressDialog.svelte';

describe('ProgressDialog image loading integration', () => {
  let mockEventSource: {
    addEventListener: ReturnType<typeof vi.fn>;
    removeEventListener: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
    onopen: (() => void) | null;
    onerror: (() => void) | null;
  };
  let imageRequestUrls: string[];
  let revokedObjectUrls: string[];
  let objectUrlIndex: number;
  let failImageRequests: boolean;
  let originalGetAnimations: PropertyDescriptor | undefined;

  beforeEach(() => {
    imageRequestUrls = [];
    revokedObjectUrls = [];
    objectUrlIndex = 0;
    failImageRequests = false;
    originalGetAnimations = Object.getOwnPropertyDescriptor(Element.prototype, 'getAnimations');
    Object.defineProperty(Element.prototype, 'getAnimations', {
      configurable: true,
      value: vi.fn(() => []),
    });
    mockEventSource = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      close: vi.fn(),
      onopen: null,
      onerror: null,
    };
    vi.stubGlobal(
      'EventSource',
      vi.fn(function (this: typeof mockEventSource) {
        return mockEventSource;
      })
    );
    vi.stubGlobal(
      'Image',
      class {
        src = '';
        async decode(): Promise<void> {}
      }
    );
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => `blob:image-${++objectUrlIndex}`);
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation((objectUrl) => {
      revokedObjectUrls.push(objectUrl);
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes('/frame') || url.startsWith('/thumbnails/')) {
          expect(init?.cache).toBe('no-store');
          expect(init?.signal).toBeInstanceOf(AbortSignal);
          imageRequestUrls.push(url);
          return failImageRequests
            ? new Response(null, { status: 500 })
            : new Response(new Blob(['png'], { type: 'image/png' }), { status: 200 });
        }
        return new Response(
          JSON.stringify({
            state: 'idle',
            sleepAfterUploadEnabled: false,
            sleepAfterUploadEffective: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      })
    );
  });

  afterEach(() => {
    cleanup();
    if (originalGetAnimations) {
      Object.defineProperty(Element.prototype, 'getAnimations', originalGetAnimations);
    } else {
      Reflect.deleteProperty(Element.prototype, 'getAnimations');
    }
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

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

  function emitSingleItemStart(title: string, videoId: string, thumbnailFilename: string): void {
    emitProgressEvent({
      kind: 'start',
      total: 1,
      completed: 0,
      items: [title],
      clips: [
        {
          group_index: 0,
          date_label: '06/27\n00:00～',
          match_name: 'Xマッチ',
          rule_name: 'ガチエリア',
          thumbnail_filename: thumbnailFilename,
          video_assets: [videoAsset(videoId)],
        },
      ],
    });
  }

  function expectOnlyDecodedImagesInDom(container: HTMLElement): void {
    for (const image of container.querySelectorAll<HTMLImageElement>('img')) {
      expect(image.getAttribute('src')).toMatch(/^blob:/);
    }
    for (const element of container.querySelectorAll<HTMLElement>('[style]')) {
      const style = element.getAttribute('style') ?? '';
      expect(style).not.toContain('/api/assets/recorded/');
      expect(style).not.toContain('/thumbnails/');
    }
  }

  function emitThreeItemProgress(): void {
    emitProgressEvent({
      kind: 'start',
      total: 3,
      completed: 0,
      items: ['active', 'next', 'later'],
      clips: [
        {
          group_index: 0,
          date_label: '06/27\n00:00～',
          match_name: 'Xマッチ',
          rule_name: 'ガチエリア',
          video_assets: [videoAsset('recorded/active-a.mkv'), videoAsset('recorded/active-b.mkv')],
        },
        {
          group_index: 1,
          date_label: '06/27\n01:00～',
          match_name: 'Xマッチ',
          rule_name: 'ガチエリア',
          video_assets: [videoAsset('recorded/next.mkv')],
        },
        {
          group_index: 2,
          date_label: '06/27\n02:00～',
          match_name: 'Xマッチ',
          rule_name: 'ガチエリア',
          video_assets: [videoAsset('recorded/later.mkv')],
        },
      ],
    });
    emitProgressEvent({
      kind: 'item_stage',
      total: 3,
      completed: 0,
      message: '結合中',
      item_index: 0,
      item_key: 'concat',
      item_label: '動画結合',
      progress_percent: 0,
    });
  }

  it('表示優先度順に画像を1件ずつ取得する', async () => {
    const { container } = render(ProgressDialog, { props: { isOpen: true } });
    await vi.waitFor(() => {
      expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
    });

    emitThreeItemProgress();

    await vi.waitFor(() => expect(imageRequestUrls).toHaveLength(5));
    expect(imageRequestUrls).toEqual([
      '/api/assets/recorded/recorded%2Factive-a.mkv/frame?t=0&w=960',
      '/api/assets/recorded/recorded%2Factive-a.mkv/frame?t=60&w=960',
      '/api/assets/recorded/recorded%2Factive-b.mkv/frame?t=60&w=960',
      '/api/assets/recorded/recorded%2Fnext.mkv/frame?t=60&w=960',
      '/api/assets/recorded/recorded%2Flater.mkv/frame?t=60&w=960',
    ]);
    expectOnlyDecodedImagesInDom(container);
  });

  it('画像未準備の完了カードは空srcや生URLをDOMへ渡さない', async () => {
    failImageRequests = true;
    const { container } = render(ProgressDialog, { props: { isOpen: true } });
    await vi.waitFor(() => {
      expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
    });

    emitSingleItemStart('pending-image', 'recorded/pending.mkv', 'pending.png');
    emitProgressEvent({
      kind: 'item_stage',
      total: 1,
      completed: 0,
      item_index: 0,
      item_key: 'save',
      item_label: '保存・整理',
    });
    emitProgressEvent({ kind: 'advance', total: 1, completed: 1 });
    emitProgressEvent({ kind: 'finish', total: 1, completed: 1, success: true });

    await vi.waitFor(() => {
      expect(container.querySelector('.waiting-video-card')).not.toBeNull();
    });
    expect(screen.queryByAltText('thumb')).not.toBeInTheDocument();
    expectOnlyDecodedImagesInDom(container);
  });

  it('完了カードのslot解放後も表示中の最後の成功画像をrevokeしない', async () => {
    const { container } = render(ProgressDialog, { props: { isOpen: true } });
    await vi.waitFor(() => {
      expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
    });

    emitSingleItemStart('stable-image', 'recorded/stable.mkv', 'stable.png');
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
      expect(screen.getByTestId('progress-main-image')).toHaveAttribute(
        'src',
        expect.stringMatching(/^blob:/)
      );
    });

    emitProgressEvent({
      kind: 'item_stage',
      total: 1,
      completed: 0,
      item_index: 0,
      item_key: 'save',
      item_label: '保存・整理',
    });
    emitProgressEvent({ kind: 'advance', total: 1, completed: 1 });
    emitProgressEvent({ kind: 'finish', total: 1, completed: 1, success: true });
    await vi.waitFor(() => {
      expect(container.querySelector('.waiting-video-card')).not.toBeNull();
      expect(screen.getByAltText('thumb')).toHaveAttribute('src', expect.stringMatching(/^blob:/));
      expect(screen.getByTestId('progress-main-image')).toHaveAttribute(
        'src',
        expect.stringMatching(/^blob:/)
      );
    });
    const retainedUrl = screen.getByTestId('progress-main-image').getAttribute('src');
    expect(retainedUrl).toMatch(/^blob:/);

    emitProgressEvent({
      task_id: 'auto_upload',
      task_name: '自動アップロード',
      kind: 'start',
      total: 1,
      completed: 0,
      items: ['stable-image'],
    });
    emitProgressEvent({
      task_id: 'auto_upload',
      task_name: '自動アップロード',
      kind: 'advance',
      total: 1,
      completed: 1,
    });
    await vi.waitFor(() => {
      expect(container.querySelector('.waiting-video-card')).toBeNull();
    });
    await Promise.resolve();
    await Promise.resolve();

    expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', retainedUrl);
    expect(revokedObjectUrls).not.toContain(retainedUrl);
    expectOnlyDecodedImagesInDom(container);
  });

  it('画像取得失敗後も進捗完了イベントを表示へ反映する', async () => {
    failImageRequests = true;
    render(ProgressDialog, { props: { isOpen: true } });
    await vi.waitFor(() => {
      expect(registeredEventHandler('progress_event')).toEqual(expect.any(Function));
    });

    emitThreeItemProgress();
    await vi.waitFor(() => expect(imageRequestUrls.length).toBeGreaterThan(0));
    emitProgressEvent({
      kind: 'finish',
      total: 3,
      completed: 3,
      success: true,
      message: '自動編集が完了しました',
    });

    await vi.waitFor(() => {
      expect(screen.getByRole('button', { name: '閉じる' })).toBeEnabled();
    });
  });
});
