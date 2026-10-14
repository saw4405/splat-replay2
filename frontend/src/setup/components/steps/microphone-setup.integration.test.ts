import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SetupStep, type SetupState } from '../../types';
import { setupState } from '../../stores/state';

const mocks = vi.hoisted(() => ({
  getTranscriptionConfig: vi.fn(),
  listMicrophones: vi.fn(),
  saveTranscriptionConfig: vi.fn(),
  checkSystem: vi.fn(),
  markSubstepCompleted: vi.fn(),
}));

vi.mock('../../platform', () => ({ getSetupPlatform: () => 'macos' }));

vi.mock('../../stores/config', () => ({
  getTranscriptionConfig: mocks.getTranscriptionConfig,
  listMicrophones: mocks.listMicrophones,
  saveTranscriptionConfig: mocks.saveTranscriptionConfig,
}));

vi.mock('../../stores/navigation', () => ({
  markSubstepCompleted: mocks.markSubstepCompleted,
}));
vi.mock('../../stores/system', () => ({
  checkSystem: mocks.checkSystem,
}));

import TranscriptionSetup from './TranscriptionSetup.svelte';

describe('microphone setup integration', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('transcription_substep_index', '1');
    const state: SetupState = {
      is_completed: false,
      current_step: SetupStep.TRANSCRIPTION_SETUP,
      completed_steps: [],
      skipped_steps: [],
      step_details: { [SetupStep.TRANSCRIPTION_SETUP]: {} },
      required_setup_issues: [],
      installation_date: null,
    };
    setupState.set(state);
    mocks.getTranscriptionConfig.mockResolvedValue({
      enabled: true,
      micDeviceName: 'Previously used USB microphone',
      groqApiKey: 'test-key',
      language: 'ja-JP',
      customDictionary: [],
      energyThreshold: 300,
    });
    mocks.listMicrophones.mockResolvedValue([]);
    mocks.checkSystem.mockResolvedValue({ is_installed: true });
    mocks.saveTranscriptionConfig.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    setupState.set(null);
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('実マイクが 0 件なら保存名だけでは手順を完了できない', async () => {
    render(TranscriptionSetup);

    expect(
      await screen.findByRole('option', {
        name: 'Previously used USB microphone（現在の一覧にありません）',
      })
    ).toBeDisabled();
    expect(
      screen.getByText(/マイク名が一覧にあるだけでは実際の収音を確認できません/)
    ).toBeInTheDocument();
    expect(screen.getByText(/マイク接続を確認してください/)).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: /マイク名の入力/ }));

    expect(await screen.findByText(/保存済みのマイクは現在の一覧にありません/)).toBeInTheDocument();
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalled();
    expect(mocks.saveTranscriptionConfig).not.toHaveBeenCalled();
  });
});
