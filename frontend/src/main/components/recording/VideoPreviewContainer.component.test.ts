import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  subscribeDomainEventsMock,
  recoverCaptureDeviceMock,
  getRecorderPreviewModeMock,
  notifyRecordingReadyMock,
  getMetadataOptionsMock,
  buildMetadataOptionMapMock,
} = vi.hoisted(() => ({
  subscribeDomainEventsMock: vi.fn(),
  recoverCaptureDeviceMock: vi.fn(),
  getRecorderPreviewModeMock: vi.fn(),
  notifyRecordingReadyMock: vi.fn(),
  getMetadataOptionsMock: vi.fn(),
  buildMetadataOptionMapMock: vi.fn(),
}));

vi.mock('../../domainEvents', () => ({
  subscribeDomainEvents: subscribeDomainEventsMock,
}));

vi.mock('../../api/recording', async () => {
  const actual = await vi.importActual<typeof import('../../api/recording')>('../../api/recording');
  return {
    ...actual,
    getRecorderPreviewMode: getRecorderPreviewModeMock,
    recoverCaptureDevice: recoverCaptureDeviceMock,
  };
});

vi.mock('../../notification', () => ({
  notifyRecordingReady: notifyRecordingReadyMock,
}));

vi.mock('../../renderMode', async () => {
  const { writable } = await import('svelte/store');
  return {
    getDeviceStatusPollIntervalMs: () => 500,
    renderMode: writable<'gpu' | 'cpu'>('gpu'),
  };
});

vi.mock('../../api/metadata', () => ({
  getMetadataOptions: getMetadataOptionsMock,
  buildMetadataOptionMap: buildMetadataOptionMapMock,
}));

vi.mock('./VideoPreview.svelte', async () => {
  const module = await import('../../../test-utils/StubComponent.svelte');
  return { default: module.default };
});

vi.mock('../metadata/MetadataOverlay.svelte', async () => {
  const module = await import('../../../test-utils/VisibleStub.svelte');
  return { default: module.default };
});

vi.mock('../permission/CameraPermissionDialog.svelte', async () => {
  const module = await import('../../../test-utils/OpenStub.svelte');
  return { default: module.default };
});

import VideoPreviewContainer from './VideoPreviewContainer.svelte';

function jsonResponse(body: unknown, status: number = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

type CapturedDomainEvent = {
  type: string;
  payload: Record<string, unknown>;
};

describe('VideoPreviewContainer.svelte', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let domainEventHandler: ((event: CapturedDomainEvent) => void) | null;

  function emitDomainEvent(event: CapturedDomainEvent): void {
    if (domainEventHandler === null) {
      throw new Error('domain event handler is not registered');
    }
    domainEventHandler(event);
  }

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
    domainEventHandler = null;

    subscribeDomainEventsMock.mockReset();
    subscribeDomainEventsMock.mockImplementation(
      (onEvent: (event: CapturedDomainEvent) => void) => {
        domainEventHandler = onEvent;
        return {
          close: vi.fn(),
          readyState: 1,
          onerror: null,
        };
      }
    );

    getRecorderPreviewModeMock.mockReset();
    getRecorderPreviewModeMock.mockResolvedValue('live_capture');

    recoverCaptureDeviceMock.mockReset();
    recoverCaptureDeviceMock.mockResolvedValue({
      attempted: true,
      recovered: false,
      message: 'recover failed',
      action: 'restart-device',
    });

    notifyRecordingReadyMock.mockReset();
    notifyRecordingReadyMock.mockResolvedValue(undefined);

    getMetadataOptionsMock.mockReset();
    getMetadataOptionsMock.mockResolvedValue({
      gameModes: [],
      matches: [],
      rules: [],
      stages: [],
      judgements: [],
    });

    buildMetadataOptionMapMock.mockReset();
    buildMetadataOptionMapMock.mockReturnValue(null);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('起動時に切断されていれば startup_auto 回復を 1 回試し、手動回復ボタンを表示する', async () => {
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(false);
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    await waitFor(() => {
      expect(recoverCaptureDeviceMock).toHaveBeenCalledWith('startup_auto');
    });

    expect(await screen.findByRole('button')).toBeInTheDocument();
  });

  it('手動回復ボタンから manual 回復を呼び出す', async () => {
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(false);
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    await waitFor(() => {
      expect(recoverCaptureDeviceMock).toHaveBeenCalledWith('startup_auto');
    });

    recoverCaptureDeviceMock.mockClear();

    const button = await screen.findByRole('button');
    await button.click();

    await waitFor(() => {
      expect(recoverCaptureDeviceMock).toHaveBeenCalledWith('manual');
    });
  });

  it('接続中から切断へ遷移したら idle_auto 回復を呼び出す', async () => {
    const deviceStatuses = [true, false];
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        const next = deviceStatuses.shift() ?? false;
        return jsonResponse(next);
      }
      if (url.includes('/api/settings/camera-permission-dialog')) {
        return jsonResponse({ shown: true });
      }
      if (url.includes('/api/recorder/prepare')) {
        return jsonResponse({ success: true });
      }
      if (url.includes('/api/recorder/enable-auto')) {
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/recorder/prepare',
        expect.objectContaining({ method: 'POST' })
      );
    });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/recorder/enable-auto',
        expect.objectContaining({ method: 'POST' })
      );
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(notifyRecordingReadyMock).toHaveBeenCalled();

    recoverCaptureDeviceMock.mockClear();
    await new Promise((resolve) => window.setTimeout(resolve, 650));

    const deviceStatusCalls = fetchMock.mock.calls.filter(([input]) =>
      input.toString().includes('/api/device/status')
    );
    expect(deviceStatusCalls).toHaveLength(1);
    expect(recoverCaptureDeviceMock).not.toHaveBeenCalledWith('idle_auto');
  });

  it('prepare 中の切断では idle_auto 回復を走らせない', async () => {
    const deviceStatuses = [true, false];
    const pendingPrepare = new Promise<Response>(() => {});
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        const next = deviceStatuses.shift() ?? false;
        return jsonResponse(next);
      }
      if (url.includes('/api/settings/camera-permission-dialog')) {
        return jsonResponse({ shown: true });
      }
      if (url.includes('/api/recorder/prepare')) {
        return pendingPrepare;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/recorder/prepare',
        expect.objectContaining({ method: 'POST' })
      );
    });

    await new Promise((resolve) => window.setTimeout(resolve, 650));

    expect(recoverCaptureDeviceMock).not.toHaveBeenCalledWith('idle_auto');
  });

  it('録画セッションが一時停止中の切断では idle_auto 回復を走らせない', async () => {
    const deviceStatuses = [true, false];
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        const next = deviceStatuses.shift() ?? false;
        return jsonResponse(next);
      }
      if (url.includes('/api/settings/camera-permission-dialog')) {
        return jsonResponse({ shown: true });
      }
      if (url.includes('/api/recorder/prepare')) {
        return jsonResponse({ success: true });
      }
      if (url.includes('/api/recorder/enable-auto')) {
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/recorder/enable-auto',
        expect.objectContaining({ method: 'POST' })
      );
    });

    emitDomainEvent({ type: 'domain.recording.started', payload: {} });
    emitDomainEvent({
      type: 'domain.recording.paused',
      payload: { reason: 'battle_finished' },
    });

    recoverCaptureDeviceMock.mockClear();
    await new Promise((resolve) => window.setTimeout(resolve, 650));

    expect(recoverCaptureDeviceMock).not.toHaveBeenCalledWith('idle_auto');
  });

  it('video_file モードでは追加の device status ポーリングをしない', async () => {
    getRecorderPreviewModeMock.mockResolvedValue('video_file');

    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(true);
      }
      if (url.includes('/api/recorder/prepare')) {
        return jsonResponse({ success: true });
      }
      if (url.includes('/api/recorder/enable-auto')) {
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/device/status',
        expect.objectContaining({ cache: 'no-store' })
      );
    });

    await new Promise((resolve) => window.setTimeout(resolve, 650));

    const deviceStatusCalls = fetchMock.mock.calls.filter(([input]) =>
      input.toString().includes('/api/device/status')
    );
    expect(deviceStatusCalls).toHaveLength(1);
  });
});
