import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { get } from 'svelte/store';
import { afterEach, describe, expect, it, vi } from 'vitest';
import OBSSetup from './OBSSetup.svelte';
import { setupState } from '../../stores/state';
import { SetupStep } from '../../types';

const mocks = vi.hoisted(() => ({
  getSetupPlatform: vi.fn(() => 'macos' as const),
  checkSystem: vi.fn(async () => ({
    is_installed: true,
    version: '6.3.2.0',
    installation_path: '/usr/local/lib/libndi.dylib',
    error_message: '',
  })),
  markSubstepCompleted: vi.fn(async () => undefined),
  getOBSConfig: vi.fn(async () => ({ websocket_password: '', capture_device_name: '' })),
  listVideoDevices: vi.fn(async () => []),
  saveCaptureDevice: vi.fn(async () => undefined),
  saveOBSWebSocketPassword: vi.fn(async () => undefined),
}));

vi.mock('../../platform', () => ({
  getSetupPlatform: mocks.getSetupPlatform,
  MACOS_APPLICATION_SUPPORT_DIR: '~/Library/Application Support/io.github.saw4405.splatreplay',
}));
vi.mock('../../stores/system', () => ({ checkSystem: mocks.checkSystem }));
vi.mock('../../stores/navigation', () => ({ markSubstepCompleted: mocks.markSubstepCompleted }));
vi.mock('../../stores/config', () => ({
  getOBSConfig: mocks.getOBSConfig,
  listVideoDevices: mocks.listVideoDevices,
  saveCaptureDevice: mocks.saveCaptureDevice,
  saveOBSWebSocketPassword: mocks.saveOBSWebSocketPassword,
}));

async function renderOBS(substepIndex: number, completedDetails: Record<string, boolean> = {}) {
  sessionStorage.clear();
  sessionStorage.setItem('obs_substep_index', String(substepIndex));

  setupState.set({
    is_completed: false,
    current_step: SetupStep.OBS_SETUP,
    completed_steps: [],
    skipped_steps: [],
    step_details: { [SetupStep.OBS_SETUP]: completedDetails },
    required_setup_issues: [],
    installation_date: null,
  });
  render(OBSSetup);
  return { setupState };
}

describe('OBS platform setup guidance', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('Apple Silicon 搭載 Mac 向けの OBS 案内を表示する', async () => {
    await renderOBS(0);

    expect(await screen.findByText(/Apple Silicon 搭載 Mac では/)).toBeInTheDocument();
  });

  it('画角確認で OBS とアプリの全面16:9を案内する', async () => {
    await renderOBS(3);

    expect(await screen.findByText(/左右の黒帯や横方向の縮みがなく/)).toBeInTheDocument();
    expect(screen.getByText(/解像度の数字だけでは画角を判断できません/)).toBeInTheDocument();
  });

  it('録画設定で音声の観測寿命とOBS入力確認を案内する', async () => {
    await renderOBS(4);

    expect(
      await screen.findByText(/Switch の電源 ON 後は OBS 音量メーターを観測します/)
    ).toBeInTheDocument();
    expect(screen.getByText(/入力と録音トラックが正しいか/)).toBeInTheDocument();
    expect(screen.getByText(/無音を理由に OBS は再起動しません/)).toBeInTheDocument();
  });

  it('Mac は DistroAV を案内し、Windows 用インストーラーを表示しない', async () => {
    await renderOBS(1);

    expect(await screen.findByText(/distroav-\*-macos-universal\.pkg/)).toBeInTheDocument();
    expect(screen.queryByText(/windows-x64-installer\.exe/)).not.toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'ダウンロードページを開く' });
    expect(link).toHaveAttribute('href', 'https://github.com/DistroAV/DistroAV/releases/latest');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('Mac は Runtime pkg と再起動・再検査を案内し、未導入なら保存済み完了を取り消す', async () => {
    const user = userEvent.setup();
    mocks.checkSystem.mockResolvedValue({
      is_installed: false,
      version: '6.2.1.0',
      installation_path: '/usr/local/lib/libndi.dylib',
      error_message: 'DistroAV 6.2.1 には NDI Runtime 6.3 以降が必要です (検出: 6.2.1.0)',
    });
    await renderOBS(2, { 'ndi-runtime': true });

    expect(await screen.findByText(/NDI Runtime 6\.3 以降の macOS 公式 pkg/)).toBeInTheDocument();
    expect(screen.getByText(/OBS を終了して再起動します/)).toBeInTheDocument();
    expect(screen.getByText(/この画面に戻り、「NDI Runtime を再検査」/)).toBeInTheDocument();
    expect(
      await screen.findByText(/DistroAV 6\.2\.1 には NDI Runtime 6\.3 以降/)
    ).toBeInTheDocument();
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith('obs_setup', 'ndi-runtime', false);

    const link = screen.getByRole('link', { name: '公式 NDI Runtime pkg を開く' });
    expect(link).toHaveAttribute('href', 'https://ndi.link/NDIRedistV6Apple');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    await user.click(screen.getByRole('button', { name: 'NDI Runtime を再検査' }));
    expect(mocks.checkSystem).toHaveBeenCalledWith('ndi');
    expect(screen.getByRole('dialog')).toHaveTextContent(/NDI Runtime 6\.3 以降が必要です/);
  });

  it('Mac の NDI 設定で Main Output を有効にする手順を表示する', async () => {
    await renderOBS(5);

    expect(await screen.findByText(/「Main Output」にチェックを入れます/)).toBeInTheDocument();
  });

  it('NDI 検査 API の失敗時も古い完了状態を解除する', async () => {
    mocks.checkSystem.mockRejectedValueOnce(new Error('check unavailable'));
    mocks.markSubstepCompleted.mockRejectedValueOnce(new Error('persistence unavailable'));
    const { setupState } = await renderOBS(2, { 'ndi-runtime': true });

    expect(await screen.findByText(/NDI Runtime の再検査に失敗しました/)).toBeInTheDocument();
    expect(get(setupState)?.step_details.obs_setup['ndi-runtime']).toBe(false);
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith('obs_setup', 'ndi-runtime', false);
  });
});
