import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { subscribeDomainEventsMock, getRecorderPreviewModeMock, getRecorderStateMock } = vi.hoisted(
  () => ({
    subscribeDomainEventsMock: vi.fn(),
    getRecorderPreviewModeMock: vi.fn(),
    getRecorderStateMock: vi.fn(),
  })
);

vi.mock('../../domainEvents', () => ({
  subscribeDomainEvents: subscribeDomainEventsMock,
}));

vi.mock('../../api/recording', async () => {
  const actual = await vi.importActual<typeof import('../../api/recording')>('../../api/recording');
  return {
    ...actual,
    getRecorderPreviewMode: getRecorderPreviewModeMock,
    getRecorderState: getRecorderStateMock,
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
    getRecorderStateMock.mockReset();
    getRecorderStateMock.mockResolvedValue('STOPPED');
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

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/recorder/preview-frame', {
        cache: 'no-store',
      });
    });
    expect(getUserMediaMock).not.toHaveBeenCalled();
    await vi.waitFor(() => {
      expect(screen.getByTestId('video-file-preview-image')).toHaveAttribute(
        'src',
        'blob:preview-frame'
      );
    });
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

    await vi.waitFor(() => {
      expect(getUserMediaMock).toHaveBeenCalledWith({
        video: { deviceId: { exact: 'camera-1' } },
        audio: false,
      });
    });
    expect(fetchMock).not.toHaveBeenCalledWith('/api/recorder/preview-frame', {
      cache: 'no-store',
    });
  });

  it('開始イベントを購読前に取り逃がしても現在状態APIからRecordingへ同期する', async () => {
    getRecorderPreviewModeMock.mockResolvedValue('video_file');
    getRecorderStateMock.mockResolvedValue('RECORDING');

    render(VideoPreview);

    expect(await screen.findByText('REC')).toBeInTheDocument();
  });

  it('Capture Controlの独立ボタンから既存の手動録画APIを呼び出す', async () => {
    getRecorderPreviewModeMock.mockResolvedValue('video_file');
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/recorder/preview-frame')) {
        return new Response(null, { status: 204 });
      }
      if (
        url.includes('/api/recorder/start') ||
        url.includes('/api/recorder/pause') ||
        url.includes('/api/recorder/resume') ||
        url.includes('/api/recorder/stop')
      ) {
        return new Response(null, { status: 200 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    getRecorderStateMock.mockResolvedValue('STOPPED');
    render(VideoPreview, { props: { switchPowerState: 'armed' } });
    let trigger = await screen.findByRole('button', {
      name: '次のバトルを自動録画する準備ができています。手動録画操作を開く',
    });
    await fireEvent.focusIn(trigger);
    await fireEvent.click(screen.getByRole('button', { name: '手動録画を開始' }));
    cleanup();

    getRecorderStateMock.mockResolvedValue('RECORDING');
    render(VideoPreview, { props: { switchPowerState: 'armed' } });
    trigger = await screen.findByRole('button', {
      name: '現在録画中です。手動録画操作を開く',
    });
    await fireEvent.focusIn(trigger);
    await fireEvent.click(screen.getByRole('button', { name: '録画を一時停止' }));
    await fireEvent.click(screen.getByRole('button', { name: '録画を停止' }));
    cleanup();

    getRecorderStateMock.mockResolvedValue('PAUSED');
    render(VideoPreview, { props: { switchPowerState: 'armed' } });
    trigger = await screen.findByRole('button', {
      name: '録画を一時停止しています。手動録画操作を開く',
    });
    await fireEvent.focusIn(trigger);
    await fireEvent.click(screen.getByRole('button', { name: '録画を再開' }));

    expect(fetchMock).toHaveBeenCalledWith('/api/recorder/start', { method: 'POST' });
    expect(fetchMock).toHaveBeenCalledWith('/api/recorder/pause', { method: 'POST' });
    expect(fetchMock).toHaveBeenCalledWith('/api/recorder/resume', { method: 'POST' });
    expect(fetchMock).toHaveBeenCalledWith('/api/recorder/stop', { method: 'POST' });
  });
});
