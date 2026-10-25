import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SetupStep, type SetupState } from '../../types';
import { setupState } from '../../stores/state';

const mocks = vi.hoisted(() => ({
  getSetupPlatform: vi.fn(() => 'macos'),
  getTranscriptionConfig: vi.fn(),
  listMicrophones: vi.fn(),
  saveTranscriptionConfig: vi.fn(),
  checkSystem: vi.fn(),
  setupFlac: vi.fn(),
  markSubstepCompleted: vi.fn(),
}));

vi.mock('../../platform', () => ({ getSetupPlatform: mocks.getSetupPlatform }));
vi.mock('../../stores/config', () => ({
  getTranscriptionConfig: mocks.getTranscriptionConfig,
  listMicrophones: mocks.listMicrophones,
  saveTranscriptionConfig: mocks.saveTranscriptionConfig,
}));
vi.mock('../../stores/system', () => ({
  checkSystem: mocks.checkSystem,
  setupFlac: mocks.setupFlac,
}));
vi.mock('../../stores/navigation', () => ({
  markSubstepCompleted: mocks.markSubstepCompleted,
}));

import TranscriptionSetup from './TranscriptionSetup.svelte';

describe('transcription FLAC setup integration', () => {
  beforeEach(() => {
    sessionStorage.clear();
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
    mocks.getSetupPlatform.mockReturnValue('macos');
    mocks.getTranscriptionConfig.mockResolvedValue({
      enabled: true,
      micDeviceName: '',
      groqApiKey: '',
      language: 'ja-JP',
      customDictionary: [],
      energyThreshold: 300,
    });
    mocks.listMicrophones.mockResolvedValue([]);
    mocks.saveTranscriptionConfig.mockResolvedValue(undefined);
    mocks.checkSystem.mockResolvedValue({
      is_installed: false,
      error_message: 'FLAC コマンドが PATH に見つかりませんでした',
    });
    mocks.setupFlac.mockResolvedValue({
      is_installed: false,
      error_message: 'Homebrew による導入に失敗しました',
    });
  });

  afterEach(() => {
    cleanup();
    setupState.set(null);
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('FLAC の導入失敗時は完了表示せず、アプリ内導入を案内する', async () => {
    const user = userEvent.setup();
    render(TranscriptionSetup);

    expect(await screen.findByText('送信されるデータとログの保存場所')).toBeInTheDocument();
    await user.click(screen.getByText('送信されるデータとログの保存場所'));
    expect(
      screen.getByText(/文字起こしを有効\/無効にする設定は次回の録画開始から反映されます/)
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Google 利用規約' })).toHaveAttribute(
      'href',
      'https://policies.google.com/terms?hl=ja'
    );
    expect(
      await screen.findByText(/FLAC コマンドが PATH に見つかりませんでした/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Homebrew がない場合は Terminal が開くことがあります/)
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Homebrew で FLAC を導入' }));

    expect(await screen.findByText(/Homebrew による導入に失敗しました/)).toBeInTheDocument();
    expect(mocks.setupFlac).toHaveBeenCalledTimes(1);
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalledWith(
      SetupStep.TRANSCRIPTION_SETUP,
      'transcription-enable',
      true
    );
  });

  it('導入後の API 検査で FLAC が確認できた時だけ準備を完了する', async () => {
    const user = userEvent.setup();
    mocks.checkSystem
      .mockResolvedValueOnce({
        is_installed: false,
        error_message: 'FLAC コマンドが PATH に見つかりませんでした',
      })
      .mockResolvedValueOnce({ is_installed: true, version: 'flac 1.4.3' });
    mocks.setupFlac.mockResolvedValueOnce({ is_installed: true, version: 'flac 1.4.3' });
    render(TranscriptionSetup);

    await screen.findByText(/FLAC コマンドが PATH に見つかりませんでした/);
    await user.click(screen.getByRole('button', { name: 'Homebrew で FLAC を導入' }));

    expect(await screen.findByText(/FLAC を確認しました \(flac 1.4.3\)/)).toBeInTheDocument();
    await waitFor(() => {
      expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
        SetupStep.TRANSCRIPTION_SETUP,
        'transcription-enable',
        true
      );
    });
    expect(mocks.checkSystem).toHaveBeenCalledTimes(2);
    expect(mocks.checkSystem).toHaveBeenNthCalledWith(1, 'flac');
    expect(mocks.checkSystem).toHaveBeenNthCalledWith(2, 'flac');
  });

  it('保存済みの文字起こし無効設定を次へ進む時に完了記録する', async () => {
    mocks.getTranscriptionConfig.mockResolvedValueOnce({
      enabled: false,
      micDeviceName: '',
      groqApiKey: '',
      language: 'ja-JP',
      customDictionary: [],
      energyThreshold: 300,
    });
    const { component } = render(TranscriptionSetup);

    await screen.findByRole('button', { name: '使用しない' });

    expect(await component.next()).toBe(false);
    expect(mocks.saveTranscriptionConfig).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false })
    );
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
      SetupStep.TRANSCRIPTION_SETUP,
      'transcription-enable',
      true
    );
  });

  it('文字起こし無効設定の保存に失敗した時は完了記録しない', async () => {
    mocks.getTranscriptionConfig.mockResolvedValueOnce({
      enabled: false,
      micDeviceName: '',
      groqApiKey: '',
      language: 'ja-JP',
      customDictionary: [],
      energyThreshold: 300,
    });
    mocks.saveTranscriptionConfig.mockRejectedValueOnce(new Error('save failed'));
    const { component } = render(TranscriptionSetup);

    await screen.findByRole('button', { name: '使用しない' });

    expect(await component.next()).toBe(true);
    expect(await screen.findByText('文字起こし設定の保存に失敗しました。')).toBeInTheDocument();
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalledWith(
      SetupStep.TRANSCRIPTION_SETUP,
      'transcription-enable',
      true
    );
  });

  it('導入 POST が成功でも GET で未導入なら準備を完了しない', async () => {
    const user = userEvent.setup();
    mocks.setupFlac.mockResolvedValueOnce({ is_installed: true, version: 'flac 1.4.3' });
    render(TranscriptionSetup);

    await screen.findByText(/FLAC コマンドが PATH に見つかりませんでした/);
    await user.click(screen.getByRole('button', { name: 'Homebrew で FLAC を導入' }));

    await waitFor(() => expect(mocks.checkSystem).toHaveBeenCalledTimes(2));
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalledWith(
      SetupStep.TRANSCRIPTION_SETUP,
      'transcription-enable',
      true
    );
  });

  it('API キー入力だけでは音声認識の成功を示さないと案内する', async () => {
    sessionStorage.setItem('transcription_substep_index', '2');
    render(TranscriptionSetup);

    expect(
      await screen.findByText(/API キーを保存しても音声認識の成功は確認できません/)
    ).toBeInTheDocument();
    expect(screen.getByText(/設定画面の「音声認識テスト」/)).toBeInTheDocument();
  });

  it('Windows の文字起こし設定では FLAC のチェックや導入を行わない', async () => {
    mocks.getSetupPlatform.mockReturnValue('windows');
    render(TranscriptionSetup);

    await screen.findByRole('button', { name: '使用する' });

    expect(mocks.checkSystem).not.toHaveBeenCalledWith('flac');
    expect(
      screen.queryByRole('button', { name: 'Homebrew で FLAC を導入' })
    ).not.toBeInTheDocument();
  });

  it('Windows では保存済みマイク名を選択肢として維持する', async () => {
    mocks.getSetupPlatform.mockReturnValue('windows');
    sessionStorage.setItem('transcription_substep_index', '1');
    mocks.getTranscriptionConfig.mockResolvedValueOnce({
      enabled: true,
      micDeviceName: 'Previously configured microphone',
      groqApiKey: '',
      language: 'ja-JP',
      customDictionary: [],
      energyThreshold: 300,
    });
    const { component } = render(TranscriptionSetup);

    expect(
      await screen.findByRole('option', { name: 'Previously configured microphone' })
    ).toBeEnabled();
    expect(mocks.checkSystem).not.toHaveBeenCalledWith('flac');
    expect(await component.next()).toBe(true);
    expect(mocks.saveTranscriptionConfig).toHaveBeenCalledTimes(1);
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
      SetupStep.TRANSCRIPTION_SETUP,
      'transcription-mic',
      true
    );
  });
});
