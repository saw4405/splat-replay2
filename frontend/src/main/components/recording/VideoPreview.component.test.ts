import { cleanup, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { subscribeDomainEventsMock, getRecorderPreviewModeMock } = vi.hoisted(() => ({
  subscribeDomainEventsMock: vi.fn(),
  getRecorderPreviewModeMock: vi.fn(),
}));

vi.mock('../../domainEvents', () => ({
  subscribeDomainEvents: subscribeDomainEventsMock,
}));

vi.mock('../../api/recording', async () => {
  const actual = await vi.importActual<typeof import('../../api/recording')>('../../api/recording');
  return {
    ...actual,
    getRecorderPreviewMode: getRecorderPreviewModeMock,
  };
});

vi.mock('../../renderMode', async () => {
  const { writable } = await import('svelte/store');
  return {
    getPreviewFramePollIntervalMs: () => 50,
    renderMode: writable<'cpu' | 'gpu'>('cpu'),
  };
});

import VideoPreview from './VideoPreview.svelte';

function installMediaDevices(mediaDevices: Partial<MediaDevices>): void {
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: mediaDevices,
  });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function flushAsyncWork(): Promise<void> {
  for (let index = 0; index < 10; index += 1) {
    await Promise.resolve();
  }
  await tick();
}

describe('VideoPreview.svelte', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let getUserMediaMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    getUserMediaMock = vi.fn();
    vi.useFakeTimers();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('location', { hostname: '127.0.0.1' });
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:preview-frame'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: vi.fn().mockResolvedValue(undefined),
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: vi.fn(),
    });
    vi.spyOn(console, 'log').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    subscribeDomainEventsMock.mockReset();
    subscribeDomainEventsMock.mockReturnValue({
      close: vi.fn(),
      onerror: null,
      readyState: 1,
    });
    getRecorderPreviewModeMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('LAN origin uses backend preview frames for live capture', async () => {
    vi.stubGlobal('location', { hostname: '192.168.1.20' });
    getRecorderPreviewModeMock.mockResolvedValue('live_capture');
    installMediaDevices({
      enumerateDevices: vi
        .fn()
        .mockResolvedValue([
          { kind: 'videoinput', label: 'OBS Virtual Camera', deviceId: 'camera-1' },
        ]),
      getUserMedia: getUserMediaMock,
    });
    fetchMock.mockResolvedValue(
      new Response(new Blob(['jpeg'], { type: 'image/jpeg' }), {
        status: 200,
        headers: { 'Content-Type': 'image/jpeg' },
      })
    );

    render(VideoPreview);

    await flushAsyncWork();

    expect(fetchMock).toHaveBeenCalledWith('/api/recorder/preview-frame', {
      cache: 'no-store',
    });
    expect(getUserMediaMock).not.toHaveBeenCalled();
    expect(screen.getByTestId('video-file-preview-image')).toHaveAttribute(
      'src',
      'blob:preview-frame'
    );
  });

  it('loopback origin keeps using the OBS virtual camera for live capture', async () => {
    vi.stubGlobal('location', { hostname: '127.0.0.1' });
    getRecorderPreviewModeMock.mockResolvedValue('live_capture');
    const mediaStream = new MediaStream();
    Object.defineProperty(mediaStream, 'getTracks', {
      configurable: true,
      value: vi.fn(() => []),
    });
    getUserMediaMock.mockResolvedValue(mediaStream);
    installMediaDevices({
      enumerateDevices: vi
        .fn()
        .mockResolvedValue([
          { kind: 'videoinput', label: 'OBS Virtual Camera', deviceId: 'camera-1' },
        ]),
      getUserMedia: getUserMediaMock,
    });
    fetchMock.mockResolvedValue(jsonResponse({ sections: [] }));

    render(VideoPreview);

    await flushAsyncWork();

    expect(getUserMediaMock).toHaveBeenCalledWith({
      video: { deviceId: { exact: 'camera-1' } },
      audio: false,
    });
    expect(fetchMock).not.toHaveBeenCalledWith('/api/recorder/preview-frame', {
      cache: 'no-store',
    });
  });
});
