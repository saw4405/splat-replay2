import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { get } from 'svelte/store';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { error, isLoading, setupState } from '../stores/state';
import { SetupStep, type RequiredSetupIssue } from '../types';
import SetupWizard from './SetupWizard.svelte';

function installationStatusResponse(
  options: {
    isCompleted?: boolean;
    currentStep?: SetupStep;
    issues?: RequiredSetupIssue[];
  } = {}
): Response {
  return new Response(
    JSON.stringify({
      is_completed: options.isCompleted ?? false,
      current_step: options.currentStep ?? SetupStep.YOUTUBE_SETUP,
      completed_steps: [],
      skipped_steps: [],
      step_details: {},
      required_setup_issues: options.issues ?? [],
      installation_date: null,
    }),
    { status: 200 }
  );
}

function youtubeCredentialsIssue(): RequiredSetupIssue {
  return {
    code: 'youtube_client_secret_invalid',
    step: SetupStep.YOUTUBE_SETUP,
    substep_id: 'youtube-place-file',
    message: '有効な YouTube OAuth client_secret.json を配置してください。',
  };
}

function issueResponse(issue: RequiredSetupIssue): Response {
  return new Response(JSON.stringify(issue), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  cleanup();
  setupState.set(null);
  isLoading.set(false);
  error.set(null);
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('SetupWizard 必須設定の修復', () => {
  it('issue の substep_id に対応するカード位置へ移動する', async () => {
    const issue = youtubeCredentialsIssue();
    const statusResponses = [
      installationStatusResponse({ isCompleted: true, issues: [issue] }),
      installationStatusResponse({ isCompleted: true, issues: [issue] }),
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), window.location.origin).pathname;
      return path === '/setup/repair/youtube_client_secret_invalid'
        ? issueResponse(issue)
        : (statusResponses.shift() ?? installationStatusResponse({ isCompleted: true }));
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(SetupWizard);

    await user.click(await screen.findByRole('button', { name: '修復する' }));

    expect(window.sessionStorage.getItem('youtube_substep_index')).toBe('4');
    expect(fetchMock).toHaveBeenCalledWith('/setup/repair/youtube_client_secret_invalid', {
      method: 'POST',
    });
    expect(await screen.findByText('ステップコンテンツがありません')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '再検査して不足一覧へ戻る' })).toBeInTheDocument();
  });

  it('legacy完了環境で修復カードから戻ると必須設定を再検査して反映する', async () => {
    const issue = youtubeCredentialsIssue();
    const statusResponses = [
      installationStatusResponse({ isCompleted: true, issues: [issue] }),
      installationStatusResponse({ isCompleted: true, issues: [issue] }),
      installationStatusResponse({ isCompleted: true }),
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), window.location.origin).pathname;
      if (path === '/setup/repair/youtube_client_secret_invalid') {
        return issueResponse(issue);
      }
      return statusResponses.shift() ?? installationStatusResponse({ isCompleted: true });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(SetupWizard);
    await user.click(await screen.findByRole('button', { name: '修復する' }));
    await user.click(await screen.findByRole('button', { name: '再検査して不足一覧へ戻る' }));

    await waitFor(() => expect(get(setupState)?.required_setup_issues).toEqual([]));
    expect(get(setupState)?.is_completed).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith('/setup/status?refresh=true');
    expect(screen.queryByText(issue.message)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '修復する' })).not.toBeInTheDocument();
  });

  it('FLAC 不足を文字起こし設定内の FLAC 案内カードへ移動する', async () => {
    const issue: RequiredSetupIssue = {
      code: 'flac_missing',
      step: SetupStep.TRANSCRIPTION_SETUP,
      substep_id: 'transcription-flac',
      message: '文字起こしに必要な FLAC が利用できません。',
    };
    const statusResponses = [
      installationStatusResponse({
        isCompleted: true,
        currentStep: SetupStep.TRANSCRIPTION_SETUP,
        issues: [issue],
      }),
      installationStatusResponse({
        isCompleted: true,
        currentStep: SetupStep.TRANSCRIPTION_SETUP,
        issues: [issue],
      }),
    ];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input), window.location.origin).pathname;
        return path === '/setup/repair/flac_missing'
          ? issueResponse(issue)
          : (statusResponses.shift() ??
              installationStatusResponse({
                isCompleted: true,
                currentStep: SetupStep.TRANSCRIPTION_SETUP,
              }));
      })
    );
    const user = userEvent.setup();

    render(SetupWizard);
    await user.click(await screen.findByRole('button', { name: '修復する' }));

    expect(window.sessionStorage.getItem('transcription_substep_index')).toBe('0');
  });

  it('complete が必須不足の 409 を返すと一覧を表示し、成功扱いにしない', async () => {
    const issue = youtubeCredentialsIssue();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), window.location.origin).pathname;
      if (path === '/setup/status') return installationStatusResponse();
      if (path === '/setup/steps/youtube_setup/complete')
        return new Response(null, { status: 200 });
      if (path === '/setup/complete') {
        return new Response(
          JSON.stringify({
            detail: {
              message: '必須設定を確認してください。',
              required_setup_issues: [issue],
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response(JSON.stringify({ detail: '予期しない API 呼び出しです。' }), {
        status: 500,
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(SetupWizard);

    await user.click(await screen.findByRole('button', { name: 'スキップ' }));

    expect(await screen.findByText(issue.message)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'アプリケーションを開始' })
    ).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/setup/complete', { method: 'POST' });
    await waitFor(() => expect(get(setupState)?.required_setup_issues).toEqual([issue]));
  });

  it('必須再確認に成功したら完了状態を保存し、成功modalやreloadを待たない', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), window.location.origin);
      if (url.pathname === '/setup/steps/youtube_setup/complete') {
        return new Response(null, { status: 200 });
      }
      if (url.pathname === '/setup/complete') {
        return new Response(null, { status: 200 });
      }
      if (url.pathname === '/setup/status' && url.searchParams.has('refresh')) {
        return installationStatusResponse({ isCompleted: true });
      }
      if (url.pathname === '/setup/status') {
        return installationStatusResponse({ currentStep: SetupStep.YOUTUBE_SETUP });
      }
      return new Response(
        JSON.stringify({ detail: `想定外の API 呼び出しです: ${init?.method}` }),
        {
          status: 500,
        }
      );
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(SetupWizard);
    await user.click(await screen.findByRole('button', { name: 'スキップ' }));

    await waitFor(() => expect(get(setupState)?.is_completed).toBe(true));
    expect(get(setupState)?.required_setup_issues).toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith('/setup/complete', { method: 'POST' });
    expect(fetchMock).toHaveBeenCalledWith('/setup/status?refresh=true');
    expect(screen.queryByRole('heading', { name: 'セットアップ完了！' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'アプリケーションを開始' })
    ).not.toBeInTheDocument();
  });

  it('repair API が失敗した場合は移動せず、最新の不足一覧を再取得する', async () => {
    const staleIssue = youtubeCredentialsIssue();
    const latestIssue: RequiredSetupIssue = {
      code: 'youtube_privacy_invalid',
      step: SetupStep.YOUTUBE_SETUP,
      substep_id: 'youtube-privacy-status',
      message: 'YouTube 動画の公開範囲を保存してください。',
    };
    const statusResponses = [
      installationStatusResponse({ isCompleted: true, issues: [staleIssue] }),
      installationStatusResponse({ isCompleted: true, issues: [latestIssue] }),
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), window.location.origin).pathname;
      if (path === '/setup/repair/youtube_client_secret_invalid') {
        return new Response(JSON.stringify({ detail: 'この項目は現在不足していません。' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return statusResponses.shift() ?? installationStatusResponse({ isCompleted: true });
    });
    vi.stubGlobal('fetch', fetchMock);
    window.sessionStorage.setItem('youtube_substep_index', '2');
    const user = userEvent.setup();

    render(SetupWizard);
    await user.click(await screen.findByRole('button', { name: '修復する' }));

    expect(await screen.findByText(latestIssue.message)).toBeInTheDocument();
    expect(screen.queryByText(staleIssue.message)).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem('youtube_substep_index')).toBe('2');
    expect(screen.queryByText('ステップコンテンツがありません')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/setup/status?refresh=true');
    await waitFor(() => expect(get(setupState)?.required_setup_issues).toEqual([latestIssue]));
  });
});
