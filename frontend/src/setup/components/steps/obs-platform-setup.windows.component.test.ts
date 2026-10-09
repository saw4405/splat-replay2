import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import OBSSetup from './OBSSetup.svelte';
import { setupState } from '../../stores/state';
import { SetupStep } from '../../types';

const mocks = vi.hoisted(() => ({
  getSetupPlatform: vi.fn(() => 'windows' as const),
  checkSystem: vi.fn(async () => ({
    is_installed: true,
    version: '6.3.2.0',
    installation_path: 'C:/Program Files/NDI/NDI 6 Runtime/v6',
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

describe('Windows OBS platform setup guidance', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('従来の obs-ndi Releases URL と exe 手順を維持する', async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    sessionStorage.setItem('obs_substep_index', '1');
    setupState.set({
      is_completed: false,
      current_step: SetupStep.OBS_SETUP,
      completed_steps: [],
      skipped_steps: [],
      step_details: { [SetupStep.OBS_SETUP]: {} },
      installation_date: null,
    });
    render(OBSSetup);

    expect(await screen.findByText(/distroav-\*-windows-x64-installer\.exe/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'ダウンロードページを開く' }));
    expect(open).toHaveBeenCalledWith('https://github.com/obs-ndi/obs-ndi/releases', '_blank');
  });

  it('Windows でも画角と音声観測の案内を表示する', async () => {
    sessionStorage.setItem('obs_substep_index', '3');
    setupState.set({
      is_completed: false,
      current_step: SetupStep.OBS_SETUP,
      completed_steps: [],
      skipped_steps: [],
      step_details: { [SetupStep.OBS_SETUP]: {} },
      installation_date: null,
    });
    render(OBSSetup);

    expect(await screen.findByText(/左右の黒帯や横方向の縮みがなく/)).toBeInTheDocument();
    expect(screen.getByText(/解像度の数字だけでは画角を判断できません/)).toBeInTheDocument();

    cleanup();
    sessionStorage.setItem('obs_substep_index', '4');
    render(OBSSetup);
    expect(
      await screen.findByText(/Switch の電源 ON 後は OBS 音量メーターを観測します/)
    ).toBeInTheDocument();
    expect(screen.getByText(/入力と録音トラックが正しいか/)).toBeInTheDocument();
  });
});
