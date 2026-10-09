import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setupState } from '../../stores/state';

const mocks = vi.hoisted(() => ({
  getSetupPlatform: vi.fn(() => 'macos'),
  checkSystem: vi.fn(async () => ({ is_installed: false })),
  setupFFMPEG: vi.fn(async () => ({
    is_installed: false,
    error_message: 'Terminal で Homebrew の導入を開始しました。完了後に再確認してください。',
  })),
  setupTesseract: vi.fn(async () => ({
    is_installed: false,
    error_message: 'Terminal で Homebrew の導入を開始しました。完了後に再確認してください。',
  })),
  markSubstepCompleted: vi.fn(async () => undefined),
}));

vi.mock('../../platform', () => ({
  getSetupPlatform: mocks.getSetupPlatform,
  MACOS_APPLICATION_SUPPORT_DIR: '~/Library/Application Support/io.github.saw4405.splatreplay',
}));

vi.mock('../../stores/system', () => ({
  checkSystem: mocks.checkSystem,
  setupFFMPEG: mocks.setupFFMPEG,
  setupTesseract: mocks.setupTesseract,
}));

vi.mock('../../stores/navigation', () => ({ markSubstepCompleted: mocks.markSubstepCompleted }));

import FFMPEGSetup from './FFMPEGSetup.svelte';
import TesseractSetup from './TesseractSetup.svelte';

describe('macOS setup instructions', () => {
  beforeEach(() => {
    mocks.getSetupPlatform.mockReturnValue('macos');
    mocks.checkSystem.mockResolvedValue({ is_installed: false });
  });

  afterEach(() => {
    cleanup();
    setupState.set(null);
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('FFmpeg の Windows 手順を隠し、導入 POST の説明を表示して GET 再検査する', async () => {
    const user = userEvent.setup();
    render(FFMPEGSetup);

    expect(
      await screen.findByText(/Homebrew が未導入の場合は公式インストーラー/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/win64-gpl-shared|C:\\ffmpeg\\bin/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'FFmpeg の導入を開始', exact: true }));

    expect(
      await screen.findByText(/Terminal で Homebrew の導入を開始しました/)
    ).toBeInTheDocument();
    expect(mocks.setupFFMPEG).toHaveBeenCalledTimes(1);
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      true
    );

    await user.click(screen.getByRole('button', { name: 'インストール状態を再確認' }));
    await waitFor(() => expect(mocks.checkSystem).toHaveBeenCalledTimes(2));
  });

  it('Tesseract の Windows 手順を隠し、導入 POST の説明を表示して GET 再検査する', async () => {
    const user = userEvent.setup();
    render(TesseractSetup);

    expect(await screen.findByText(/日本語 OCR データの導入を開始します/)).toBeInTheDocument();
    expect(screen.queryByText(/tesseract-ocr-w64-setup|C:\\Program Files/)).not.toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole('button', {
          name: 'Tesseract と日本語 OCR データの導入を開始',
          exact: true,
        })
      ).toBeEnabled();
    });
    await user.click(
      screen.getByRole('button', {
        name: 'Tesseract と日本語 OCR データの導入を開始',
        exact: true,
      })
    );

    expect(
      await screen.findByText(/Terminal で Homebrew の導入を開始しました/)
    ).toBeInTheDocument();
    expect(mocks.setupTesseract).toHaveBeenCalledTimes(1);
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      true
    );

    await user.click(screen.getByRole('button', { name: 'インストール状態を再確認' }));
    await waitFor(() => expect(mocks.checkSystem).toHaveBeenCalledTimes(2));
  });

  it('GET で Tesseract と日本語データが確認できたときだけ両サブステップを完了する', async () => {
    const user = userEvent.setup();
    mocks.checkSystem
      .mockResolvedValueOnce({ is_installed: false })
      .mockResolvedValueOnce({ is_installed: true, version: '5.5.0' });
    render(TesseractSetup);

    await waitFor(() => expect(mocks.checkSystem).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole('button', { name: 'インストール状態を再確認' }));

    await waitFor(() => {
      expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
        expect.anything(),
        'tesseract-install',
        true
      );
      expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
        expect.anything(),
        'tesseract-lang-data',
        true
      );
    });
  });

  it('POST が installed を返しても、その後の GET が未導入なら完了しない', async () => {
    const user = userEvent.setup();
    mocks.setupTesseract.mockResolvedValueOnce({ is_installed: true, version: '5.5.0' });
    render(TesseractSetup);

    await waitFor(() => expect(mocks.checkSystem).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      expect(
        screen.getByRole('button', {
          name: 'Tesseract と日本語 OCR データの導入を開始',
          exact: true,
        })
      ).toBeEnabled();
    });
    await user.click(
      screen.getByRole('button', {
        name: 'Tesseract と日本語 OCR データの導入を開始',
        exact: true,
      })
    );

    expect(
      await screen.findByText(/導入後に、インストール状態を再確認してください/)
    ).toBeInTheDocument();
    expect(mocks.checkSystem).toHaveBeenCalledTimes(2);
    expect(mocks.markSubstepCompleted).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      true
    );
  });
});
