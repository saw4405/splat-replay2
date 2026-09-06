import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  subscribeDomainEventsMock,
  recoverCaptureDeviceMock,
  getAutoRecorderStateMock,
  getRecorderPreviewModeMock,
  getMetadataOptionsMock,
  buildMetadataOptionMapMock,
} = vi.hoisted(() => ({
  subscribeDomainEventsMock: vi.fn(),
  recoverCaptureDeviceMock: vi.fn(),
  getAutoRecorderStateMock: vi.fn(),
  getRecorderPreviewModeMock: vi.fn(),
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
    getAutoRecorderState: getAutoRecorderStateMock,
    getRecorderPreviewMode: getRecorderPreviewModeMock,
    recoverCaptureDevice: recoverCaptureDeviceMock,
  };
});

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
  const module = await import('./VideoPreviewTestStub.svelte');
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
    getAutoRecorderStateMock.mockReset();
    getAutoRecorderStateMock.mockResolvedValue({
      state: 'running',
      power_state: 'armed',
    });

    recoverCaptureDeviceMock.mockReset();
    recoverCaptureDeviceMock.mockResolvedValue({
      attempted: true,
      recovered: false,
      message: 'recover failed',
      action: 'restart-device',
    });

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

  it('接続時は録画準備だけを行い、自動録画の開始をブラウザから要求しない', async () => {
    vi.useFakeTimers();
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

    await vi.advanceTimersByTimeAsync(100);
    await vi.runOnlyPendingTimersAsync();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/recorder/prepare',
      expect.objectContaining({ method: 'POST' })
    );
    expect(
      fetchMock.mock.calls.some(([input]) => input.toString().includes('/api/recorder/enable-auto'))
    ).toBe(false);

    recoverCaptureDeviceMock.mockClear();
    await vi.advanceTimersByTimeAsync(650);

    const deviceStatusCalls = fetchMock.mock.calls.filter(([input]) =>
      input.toString().includes('/api/device/status')
    );
    expect(deviceStatusCalls).toHaveLength(1);
    expect(recoverCaptureDeviceMock).not.toHaveBeenCalledWith('idle_auto');
  });

  it('prepare 中の切断では idle_auto 回復を走らせない', async () => {
    vi.useFakeTimers();
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

    await vi.advanceTimersByTimeAsync(100);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/recorder/prepare',
      expect.objectContaining({ method: 'POST' })
    );

    await vi.advanceTimersByTimeAsync(650);

    expect(recoverCaptureDeviceMock).not.toHaveBeenCalledWith('idle_auto');
  });

  it('録画セッションが一時停止中の切断では idle_auto 回復を走らせない', async () => {
    vi.useFakeTimers();
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

    await vi.advanceTimersByTimeAsync(100);
    await vi.runOnlyPendingTimersAsync();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/recorder/prepare',
      expect.objectContaining({ method: 'POST' })
    );

    emitDomainEvent({ type: 'domain.recording.started', payload: {} });
    emitDomainEvent({
      type: 'domain.recording.paused',
      payload: { reason: 'battle_finished' },
    });

    recoverCaptureDeviceMock.mockClear();
    await vi.advanceTimersByTimeAsync(650);

    expect(recoverCaptureDeviceMock).not.toHaveBeenCalledWith('idle_auto');
  });

  it('video_file モードでは追加の device status ポーリングをしない', async () => {
    vi.useFakeTimers();
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

    await vi.advanceTimersByTimeAsync(100);
    await vi.runOnlyPendingTimersAsync();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/device/status',
      expect.objectContaining({ cache: 'no-store' })
    );

    await vi.advanceTimersByTimeAsync(650);

    const deviceStatusCalls = fetchMock.mock.calls.filter(([input]) =>
      input.toString().includes('/api/device/status')
    );
    expect(deviceStatusCalls).toHaveLength(1);
  });

  it('音声ヘルス警告は短い文言で表示し、詳細をツールチップに載せる', async () => {
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(true);
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

    emitDomainEvent({
      type: 'domain.recording.audio_health_checked',
      payload: {
        healthy: false,
        input_name: 'MiraBox Capture',
        status: 'silent',
        short_message: '音声入力なし',
        details: 'OBS の入力「MiraBox Capture」の音量メーターが振れていません。録画は継続します。',
      },
    });

    const warning = await screen.findByTestId('audio-health-warning');
    expect(warning).toHaveTextContent('音声入力なし');
    expect(warning).not.toHaveTextContent('音量メーターが振れていません');
    expect(warning).toHaveAttribute(
      'title',
      'OBS の入力「MiraBox Capture」の音量メーターが振れていません。録画は継続します。'
    );
  });

  it('Switch電源OFFのskipped通知で既存の音声警告を消す', async () => {
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(true);
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

    emitDomainEvent({
      type: 'domain.recording.audio_health_checked',
      payload: {
        healthy: false,
        status: 'silent',
        short_message: '音声入力なし',
        details: '音声を確認できません。',
      },
    });
    expect(await screen.findByTestId('audio-health-warning')).toBeInTheDocument();

    emitDomainEvent({
      type: 'domain.recording.audio_health_checked',
      payload: {
        healthy: true,
        status: 'skipped',
        short_message: '',
        details: 'Switch の電源ONを待機しています。',
      },
    });

    await waitFor(() => {
      expect(screen.queryByTestId('audio-health-warning')).not.toBeInTheDocument();
    });
  });

  it('Switch電源OFF中はON待機状態を表示し、再有効化APIを呼ばない', async () => {
    getAutoRecorderStateMock.mockResolvedValue({
      state: 'running',
      power_state: 'waiting_for_power_on',
    });
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(true);
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

    expect(await screen.findByTestId('video-preview-stub')).toHaveAttribute(
      'data-switch-power-state',
      'waiting_for_power_on'
    );
    expect(screen.queryByText('Switch 電源ON待機中')).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) => input.toString().includes('/api/recorder/enable-auto'))
    ).toBe(false);
  });

  it('キャプチャーデバイス切断をSwitch電源OFFと別表示する', async () => {
    getAutoRecorderStateMock.mockResolvedValue({
      state: 'running',
      power_state: 'capture_disconnected',
    });
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/device/status')) {
        return jsonResponse(true);
      }
      if (url.includes('/api/settings/camera-permission-dialog')) {
        return jsonResponse({ shown: true });
      }
      if (url.includes('/api/recorder/prepare')) {
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(VideoPreviewContainer);

    expect(await screen.findByTestId('video-preview-stub')).toHaveAttribute(
      'data-switch-power-state',
      'capture_disconnected'
    );
    expect(screen.queryByText('キャプチャーデバイス再接続待機中')).not.toBeInTheDocument();
    expect(screen.queryByText('Switch 電源ON待機中')).not.toBeInTheDocument();
  });
});
