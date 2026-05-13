import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { subscribeDomainEventsMock } = vi.hoisted(() => ({
  subscribeDomainEventsMock: vi.fn(),
}));

vi.mock('../../domainEvents', () => ({
  subscribeDomainEvents: subscribeDomainEventsMock,
}));

vi.mock('../../renderMode', async () => {
  const { writable } = await import('svelte/store');
  return {
    getProcessStatusPollIntervalMs: () => 50,
    renderMode: writable<'cpu' | 'gpu'>('cpu'),
  };
});

vi.mock('../assets/RecordedDataList.svelte', async () => {
  const module = await import('../../../test-utils/StubComponent.svelte');
  return { default: module.default };
});

vi.mock('../assets/EditedDataList.svelte', async () => {
  const module = await import('../../../test-utils/StubComponent.svelte');
  return { default: module.default };
});

vi.mock('../assets/StatisticsDataView.svelte', async () => {
  const module = await import('../../../test-utils/StubComponent.svelte');
  return { default: module.default };
});

vi.mock('../../../common/components/NotificationDialog.svelte', async () => {
  const module = await import('../../../test-utils/NotificationDialogStub.svelte');
  return { default: module.default };
});

vi.mock('../permission/YouTubePermissionDialog.svelte', async () => {
  const module = await import('../../../test-utils/OpenDialogStub.svelte');
  return { default: module.default };
});

vi.mock('../progress/ProgressDialog.svelte', async () => {
  const module = await import('../../../test-utils/ProgressDialogStub.svelte');
  return { default: module.default };
});

import BottomDrawer from './BottomDrawer.svelte';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

type CapturedDomainEvent = {
  type: string;
  payload: Record<string, unknown>;
};

describe('BottomDrawer.svelte', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let domainEventHandler: ((event: CapturedDomainEvent) => void) | null;
  let setIntervalSpy: ReturnType<typeof vi.spyOn>;

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
    setIntervalSpy = vi.spyOn(window, 'setInterval');

    subscribeDomainEventsMock.mockReset();
    subscribeDomainEventsMock.mockImplementation(
      (onEvent: (event: CapturedDomainEvent) => void) => {
        domainEventHandler = onEvent;
        return {
          close: vi.fn(),
          readyState: 1,
          onerror: null,
          onopen: null,
        };
      }
    );
  });

  afterEach(() => {
    cleanup();
    setIntervalSpy.mockRestore();
    vi.restoreAllMocks();
  });

  function installDefaultResponses(processStatuses: Array<Record<string, unknown>>): void {
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/assets/recorded')) {
        return jsonResponse([
          {
            id: 'recorded-1',
            path: '/tmp/recorded-1.mp4',
            filename: 'recorded-1.mp4',
            started_at: null,
            game_mode: null,
            match: null,
            rule: null,
            stage: null,
            rate: null,
            judgement: null,
            kill: null,
            death: null,
            special: null,
            gold_medals: null,
            silver_medals: null,
            allies: null,
            enemies: null,
            hazard: null,
            golden_egg: null,
            power_egg: null,
            rescue: null,
            rescued: null,
            has_subtitle: false,
            has_thumbnail: false,
            duration_seconds: null,
            size_bytes: null,
          },
        ]);
      }
      if (url.includes('/api/assets/edited')) {
        return jsonResponse([]);
      }
      if (url.includes('/api/history/battle')) {
        return jsonResponse({ records: [] });
      }
      if (url.includes('/api/settings/youtube-permission-dialog')) {
        return jsonResponse({ shown: true });
      }
      if (url.includes('/api/process/status')) {
        const next = processStatuses.shift() ?? {
          state: 'idle',
          started_at: null,
          finished_at: null,
          error: null,
          sleep_after_upload_default: false,
          sleep_after_upload_effective: false,
          sleep_after_upload_overridden: false,
        };
        return jsonResponse(next);
      }
      if (url.includes('/api/process/edit-upload')) {
        return jsonResponse(
          {
            accepted: false,
            status: {
              state: 'running',
              started_at: '2026-05-07T00:00:00.000Z',
              finished_at: null,
              error: null,
              sleep_after_upload_default: false,
              sleep_after_upload_effective: false,
              sleep_after_upload_overridden: false,
            },
            message: 'already running',
          },
          409
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
  }

  it('mount 時に process/status が running なら ProgressDialog を開き、status polling を開始する', async () => {
    installDefaultResponses([
      {
        state: 'running',
        started_at: '2026-05-07T00:00:00.000Z',
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
    ]);

    render(BottomDrawer);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/process/status',
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: 'application/json',
          }),
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('progress-dialog-stub')).toHaveAttribute('data-is-open', 'true');
    });

    expect(setIntervalSpy).toHaveBeenCalled();
  });

  it('domain.process.started 受信時に process/status が running なら ProgressDialog を開き、status polling を開始する', async () => {
    installDefaultResponses([
      {
        state: 'idle',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
      {
        state: 'running',
        started_at: '2026-05-07T00:00:00.000Z',
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
    ]);

    render(BottomDrawer);

    await waitFor(() => {
      expect(screen.getByTestId('progress-dialog-stub')).toHaveAttribute('data-is-open', 'false');
    });

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(([input]) => input.toString().includes('/api/process/status'))
      ).toHaveLength(1);
    });

    await Promise.resolve();
    await Promise.resolve();

    emitDomainEvent({
      type: 'domain.process.started',
      payload: {},
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/process/status',
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: 'application/json',
          }),
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('progress-dialog-stub')).toHaveAttribute('data-is-open', 'true');
    });

    expect(setIntervalSpy).toHaveBeenCalled();
  });

  it('accepted=false でも返却 status が running なら ProgressDialog に合流する', async () => {
    installDefaultResponses([
      {
        state: 'idle',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
    ]);

    render(BottomDrawer);

    await waitFor(() => {
      expect(screen.getByTestId('drawer-process-button')).not.toBeDisabled();
    });

    await screen.getByTestId('drawer-process-button').click();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/process/edit-upload',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            Accept: 'application/json',
          }),
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('progress-dialog-stub')).toHaveAttribute('data-is-open', 'true');
    });

    expect(setIntervalSpy).toHaveBeenCalled();
  });

  it('編集アップロード成功ダイアログを閉じると自動録画の再有効化を要求する', async () => {
    installDefaultResponses([
      {
        state: 'idle',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
    ]);
    const onAutoRecordingRearmRequest = vi.fn();

    render(BottomDrawer, { props: { onAutoRecordingRearmRequest } });

    await waitFor(() => {
      expect(domainEventHandler).not.toBeNull();
    });

    emitDomainEvent({
      type: 'domain.process.edit_upload_completed',
      payload: {
        success: true,
        message: '編集・アップロード処理が完了しました',
        sleep_after_upload: false,
        trigger: 'auto',
      },
    });

    await screen.findByTestId('notification-dialog-stub');
    await screen.getByTestId('notification-dialog-close').click();

    expect(onAutoRecordingRearmRequest).toHaveBeenCalledTimes(1);
  });

  it('編集アップロード失敗ダイアログを閉じても自動録画の再有効化を要求しない', async () => {
    installDefaultResponses([
      {
        state: 'idle',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
    ]);
    const onAutoRecordingRearmRequest = vi.fn();

    render(BottomDrawer, { props: { onAutoRecordingRearmRequest } });

    await waitFor(() => {
      expect(domainEventHandler).not.toBeNull();
    });

    emitDomainEvent({
      type: 'domain.process.edit_upload_completed',
      payload: {
        success: false,
        message: 'upload failed',
        sleep_after_upload: false,
        trigger: 'auto',
      },
    });

    await screen.findByTestId('notification-dialog-stub');
    await screen.getByTestId('notification-dialog-close').click();

    expect(onAutoRecordingRearmRequest).not.toHaveBeenCalled();
  });
});
