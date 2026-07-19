import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  PROGRESS_IMAGE_PRIORITY,
  ProgressImageLoader,
  type ProgressImageReady,
  type ProgressImageRequest,
} from './progressImageLoader';

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function pngResponse(): Response {
  return new Response(new Blob(['png'], { type: 'image/png' }), {
    status: 200,
    headers: { 'Content-Type': 'image/png' },
  });
}

function requestFor(
  overrides: Partial<ProgressImageRequest> & Pick<ProgressImageRequest, 'url' | 'onReady'>
): ProgressImageRequest {
  return {
    ownerId: 'owner',
    slotId: 'slot',
    priority: PROGRESS_IMAGE_PRIORITY.LATER_ITEM,
    sequence: 0,
    onError: vi.fn(),
    ...overrides,
  };
}

describe('ProgressImageLoader', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('実行中の1件を中断せず完了後に最新の優先度と投入順で次を取得する', async () => {
    const first = deferred<Response>();
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValue(pngResponse());
    let objectUrlIndex = 0;
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => `blob:${++objectUrlIndex}`),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/later', slotId: 'later', sequence: 0, onReady: vi.fn() }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.request(
      requestFor({
        url: '/next',
        slotId: 'next',
        priority: PROGRESS_IMAGE_PRIORITY.NEXT_ITEM,
        sequence: 1,
        onReady: vi.fn(),
      })
    );
    loader.request(
      requestFor({
        url: '/main',
        slotId: 'main',
        priority: PROGRESS_IMAGE_PRIORITY.MAIN,
        sequence: 2,
        onReady: vi.fn(),
      })
    );

    first.resolve(pngResponse());
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(3));

    expect(fetchFn.mock.calls.map(([url]) => url)).toEqual(['/later', '/main', '/next']);
    loader.dispose();
  });

  it('同じURLを1回だけ取得し複数slotへ同じObject URLを通知する', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(pngResponse());
    const firstReady = vi.fn<(image: ProgressImageReady) => void>();
    const secondReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:shared'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/same', slotId: 'a', onReady: firstReady }));
    loader.request(requestFor({ url: '/same', slotId: 'b', onReady: secondReady }));

    await vi.waitFor(() => expect(secondReady).toHaveBeenCalledTimes(1));
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(firstReady.mock.calls[0][0].objectUrl).toBe('blob:shared');
    expect(secondReady.mock.calls[0][0].objectUrl).toBe('blob:shared');
    loader.dispose();
  });

  it('同じslotへ同じURLを再登録しても再取得・再通知しない', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(pngResponse());
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:stable'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });
    const request = requestFor({ url: '/stable', onReady });

    loader.request(request);
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    loader.request(request);

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledTimes(1);
    loader.dispose();
  });

  it('同じslotのURL更新後に旧要求が成功しても通知しない', async () => {
    const oldResponse = deferred<Response>();
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(() => oldResponse.promise)
      .mockResolvedValue(pngResponse());
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn((blob: Blob) => `blob:${blob.size}:${fetchFn.mock.calls.length}`),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/old', onReady }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.request(requestFor({ url: '/new', onReady }));
    oldResponse.resolve(pngResponse());

    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(onReady.mock.calls[0][0].sourceUrl).toBe('/new');
    loader.dispose();
  });

  it('失敗時に250msと750msを待って合計3回試行する', async () => {
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError('network-1'))
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
      .mockResolvedValueOnce(pngResponse());
    const sleep = vi.fn().mockResolvedValue(undefined);
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:retry'),
      revokeObjectUrl: vi.fn(),
      sleep,
    });

    loader.request(requestFor({ url: '/retry', onReady }));

    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(sleep.mock.calls.map(([delay]) => delay)).toEqual([250, 750]);
    expect(fetchFn).toHaveBeenCalledWith(
      '/retry',
      expect.objectContaining({ cache: 'no-store', signal: expect.any(AbortSignal) })
    );
    loader.dispose();
  });

  it('デコード失敗時は候補Object URLを解放して同じ上限で再試行する', async () => {
    const decodeImage = vi
      .fn()
      .mockRejectedValueOnce(new Error('decode failed'))
      .mockResolvedValueOnce(undefined);
    const revokeObjectUrl = vi.fn();
    const sleep = vi.fn().mockResolvedValue(undefined);
    let objectUrlIndex = 0;
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn: vi.fn<typeof fetch>().mockResolvedValue(pngResponse()),
      decodeImage,
      createObjectUrl: vi.fn(() => `blob:decode-${++objectUrlIndex}`),
      revokeObjectUrl,
      sleep,
    });

    loader.request(requestFor({ url: '/decode', onReady }));

    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(decodeImage).toHaveBeenCalledTimes(2);
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:decode-1');
    expect(sleep).toHaveBeenCalledWith(250, expect.any(AbortSignal));
    loader.dispose();
  });

  it('最後の購読者を実行中に解放するとabortしonErrorへ通知しない', async () => {
    let observedSignal: AbortSignal | undefined;
    const fetchFn = vi.fn<typeof fetch>((_input, init) => {
      observedSignal = init?.signal ?? undefined;
      return new Promise<Response>((_resolve, reject) => {
        observedSignal?.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true }
        );
      });
    });
    const onError = vi.fn<(error: Error) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:unused'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/pending', onReady: vi.fn(), onError }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.releaseSlot('owner', 'slot');

    expect(observedSignal?.aborted).toBe(true);
    await vi.waitFor(() => expect(onError).not.toHaveBeenCalled());
    loader.dispose();
  });

  it('abortした旧generationのsettle後に同じURLの新generationを取得する', async () => {
    const oldResponse = deferred<Response>();
    let oldSignal: AbortSignal | undefined;
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockImplementationOnce((_input, init) => {
        oldSignal = init?.signal ?? undefined;
        return oldResponse.promise;
      })
      .mockResolvedValueOnce(pngResponse());
    const oldReady = vi.fn<(image: ProgressImageReady) => void>();
    const newReady = vi.fn<(image: ProgressImageReady) => void>();
    const onError = vi.fn<(error: Error) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:new-generation'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/same', onReady: oldReady, onError }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.releaseSlot('owner', 'slot');
    expect(oldSignal?.aborted).toBe(true);

    loader.request(requestFor({ url: '/same', onReady: newReady, onError }));
    expect(fetchFn).toHaveBeenCalledTimes(1);
    oldResponse.reject(new DOMException('Aborted', 'AbortError'));

    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(newReady).toHaveBeenCalledTimes(1));
    expect(fetchFn.mock.calls.map(([url]) => url)).toEqual(['/same', '/same']);
    expect(oldReady).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    loader.dispose();
  });

  it('clearした旧generationのsettleが同じURLの新generationを削除しない', async () => {
    const oldResponse = deferred<Response>();
    let oldSignal: AbortSignal | undefined;
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockImplementationOnce((_input, init) => {
        oldSignal = init?.signal ?? undefined;
        return oldResponse.promise;
      })
      .mockResolvedValueOnce(pngResponse());
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const onError = vi.fn<(error: Error) => void>();
    const revokeObjectUrl = vi.fn();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:after-clear'),
      revokeObjectUrl,
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/same', onReady: vi.fn(), onError }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.clear();
    expect(oldSignal?.aborted).toBe(true);

    loader.request(requestFor({ url: '/same', onReady, onError }));
    expect(fetchFn).toHaveBeenCalledTimes(1);
    oldResponse.reject(new DOMException('Aborted', 'AbortError'));

    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(onError).not.toHaveBeenCalled();
    loader.releaseSlot('owner', 'slot');
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:after-clear');
    loader.dispose();
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
  });

  it('共有Object URLは最後の購読者を解放した時だけ一度解放する', async () => {
    const revokeObjectUrl = vi.fn();
    const loader = new ProgressImageLoader({
      fetchFn: vi.fn<typeof fetch>().mockResolvedValue(pngResponse()),
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:shared'),
      revokeObjectUrl,
      sleep: vi.fn().mockResolvedValue(undefined),
    });
    const ready = vi.fn<(image: ProgressImageReady) => void>();

    loader.request(requestFor({ url: '/same', slotId: 'a', onReady: ready }));
    loader.request(requestFor({ url: '/same', slotId: 'b', onReady: ready }));
    await vi.waitFor(() => expect(ready).toHaveBeenCalledTimes(2));

    loader.releaseSlot('owner', 'a');
    expect(revokeObjectUrl).not.toHaveBeenCalled();
    loader.releaseSlot('owner', 'b');
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
    loader.dispose();
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
  });
});
