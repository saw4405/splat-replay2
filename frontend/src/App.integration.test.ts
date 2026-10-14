import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { get } from 'svelte/store';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App.svelte';
import { error, isLoading, setupState } from './setup/stores/state';
import { SetupStep, type RequiredSetupIssue, type SetupPlatform } from './setup/types';

vi.mock('./main/renderMode', () => ({
  initializeRenderMode: vi.fn(async () => undefined),
  setRenderMode: vi.fn(),
}));
vi.mock('./main/MainApp.svelte', async () => ({
  default: (await import('./test-utils/VisibleStub.svelte')).default,
}));

const originalNavigatorPlatform = Object.getOwnPropertyDescriptor(navigator, 'platform');
const HARDWARE_PC_SUBSTEP_INDEX = '2';

function installationStatusResponse(
  serverPlatform?: string,
  isCompleted = false,
  requiredSetupIssues: RequiredSetupIssue[] = [],
  currentStep: SetupStep = SetupStep.HARDWARE_CHECK
): Response {
  const body: Record<string, unknown> = {
    is_completed: isCompleted,
    current_step: currentStep,
    completed_steps: [],
    skipped_steps: [],
    step_details: {},
    required_setup_issues: requiredSetupIssues,
    installation_date: null,
  };
  if (serverPlatform !== undefined) body.server_platform = serverPlatform;
  return new Response(JSON.stringify(body), { status: 200 });
}

function setClientPlatform(platform: string): void {
  Object.defineProperty(navigator, 'platform', {
    configurable: true,
    value: platform,
  });
}

afterEach(() => {
  cleanup();
  setupState.set(null);
  error.set(null);
  window.sessionStorage.removeItem('hardware_substep_index');
  vi.unstubAllGlobals();
  if (originalNavigatorPlatform) {
    Object.defineProperty(navigator, 'platform', originalNavigatorPlatform);
  } else {
    Reflect.deleteProperty(navigator, 'platform');
  }
});

describe('App setup platform integration', () => {
  it('遅延・失敗・unknown・欠落時はセットアップを止め、再取得成功後に進める', async () => {
    setupState.set({
      is_completed: false,
      current_step: SetupStep.HARDWARE_CHECK,
      completed_steps: [],
      skipped_steps: [],
      step_details: {},
      required_setup_issues: [],
      installation_date: null,
      server_platform: 'windows',
    });
    setClientPlatform('Win32');

    let resolveInitial!: (response: Response) => void;
    const initialResponse = new Promise<Response>((resolve) => {
      resolveInitial = resolve;
    });
    const responses: Array<Response | Promise<Response>> = [
      initialResponse,
      installationStatusResponse('unknown'),
      installationStatusResponse(),
      installationStatusResponse('macos'),
    ];
    const fetchMock = vi.fn(async () => {
      return (await responses.shift()) ?? installationStatusResponse('macos');
    });
    vi.stubGlobal('fetch', fetchMock);
    window.sessionStorage.setItem('hardware_substep_index', HARDWARE_PC_SUBSTEP_INDEX);

    const user = userEvent.setup();
    render(App);

    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    expect(screen.queryByText('準備するもの')).not.toBeInTheDocument();
    await waitFor(() => expect(get(setupState)).toBeNull());
    resolveInitial(new Response(JSON.stringify({ detail: 'server unavailable' }), { status: 503 }));

    expect(await screen.findByRole('button', { name: '再試行' })).toBeInTheDocument();
    expect(screen.queryByText('Splat Replay セットアップ')).not.toBeInTheDocument();
    expect(get(setupState)).toBeNull();
    expect(get(error)?.error).toBe('server unavailable');

    await user.click(screen.getByRole('button', { name: '再試行' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(get(isLoading)).toBe(false));
    await waitFor(() => expect(get(setupState)?.server_platform).toBe('unknown'));
    expect(screen.queryByText('準備するもの')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '再試行' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(get(isLoading)).toBe(false));
    await waitFor(() => expect(get(setupState)?.server_platform).toBeUndefined());
    expect(screen.queryByText('準備するもの')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '再試行' }));
    expect(await screen.findByText(/^Apple Silicon 搭載 Mac、/)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    await waitFor(() => expect(get(isLoading)).toBe(false));
    expect(get(setupState)?.server_platform).toBe('macos');
    expect(fetchMock).toHaveBeenCalledWith('/setup/status');
  });

  it.each([
    ['macos', 'iPhone', /^Apple Silicon 搭載 Mac、/],
    ['windows', 'MacIntel', /Windows 11、メモリ/],
  ] as const)(
    'server %s の案内を client %s に表示する',
    async (serverPlatform: SetupPlatform, clientPlatform: string, guidance: RegExp) => {
      setClientPlatform(clientPlatform);
      window.sessionStorage.setItem('hardware_substep_index', HARDWARE_PC_SUBSTEP_INDEX);
      const fetchMock = vi.fn(async () => installationStatusResponse(serverPlatform));
      vi.stubGlobal('fetch', fetchMock);

      render(App);

      expect(await screen.findByText(guidance)).toBeInTheDocument();
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
      await waitFor(() => expect(get(isLoading)).toBe(false));
      expect(get(setupState)?.server_platform).toBe(serverPlatform);
    }
  );

  it('unknown OSでもセットアップ完了済みならメイン画面を表示する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => installationStatusResponse('unknown', true))
    );

    render(App);

    expect(await screen.findByTestId('visible-stub')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '再試行' })).not.toBeInTheDocument();
  });

  it('完了履歴があっても必須設定不足があれば通常画面を表示しない', async () => {
    const issue: RequiredSetupIssue = {
      code: 'youtube_credentials_missing',
      step: SetupStep.YOUTUBE_SETUP,
      substep_id: 'youtube-place-file',
      message: 'YouTube 認証情報ファイルを配置してください。',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        installationStatusResponse('windows', true, [issue], SetupStep.YOUTUBE_SETUP)
      )
    );

    render(App);

    expect(await screen.findByText(issue.message)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '修復する' })).toBeInTheDocument();
    expect(screen.queryByTestId('visible-stub')).not.toBeInTheDocument();
  });

  it('必須設定一覧を読めない完了レスポンスでは通常画面を表示しない', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              is_completed: true,
              current_step: SetupStep.YOUTUBE_SETUP,
              completed_steps: [],
              skipped_steps: [],
              step_details: {},
              installation_date: null,
              server_platform: 'windows',
            }),
            { status: 200 }
          )
      )
    );

    render(App);

    expect(await screen.findByRole('button', { name: '再試行' })).toBeInTheDocument();
    expect(screen.queryByTestId('visible-stub')).not.toBeInTheDocument();
    expect(get(setupState)).toBeNull();
  });
});
