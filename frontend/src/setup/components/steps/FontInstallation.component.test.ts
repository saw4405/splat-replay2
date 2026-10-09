import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setupState } from '../../stores/state';
import { SetupStep } from '../../types';

const mocks = vi.hoisted(() => ({
  checkSystem: vi.fn(async () => ({ is_installed: false })),
  markSubstepCompleted: vi.fn(async () => undefined),
}));

vi.mock('../../stores/system', () => ({ checkSystem: mocks.checkSystem }));
vi.mock('../../stores/navigation', () => ({ markSubstepCompleted: mocks.markSubstepCompleted }));

import FontInstallation from './FontInstallation.svelte';

describe('FontInstallation', () => {
  beforeEach(() => {
    setupState.set({
      is_completed: false,
      current_step: SetupStep.FONT_INSTALLATION,
      completed_steps: [],
      skipped_steps: [],
      step_details: {
        [SetupStep.FONT_INSTALLATION]: {
          'font-download': false,
          'font-place': false,
        },
      },
      installation_date: null,
    });
    sessionStorage.setItem('font_substep_index', '1');
    mocks.checkSystem.mockResolvedValue({ is_installed: false });
  });

  afterEach(() => {
    cleanup();
    setupState.set(null);
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('uses the OS Japanese font when ikamodoki1.ttf is absent', async () => {
    mocks.checkSystem.mockResolvedValue({
      is_installed: true,
      installation_path: '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
    });

    render(FontInstallation);

    expect(
      await screen.findByText('ikamodoki1.ttf がないため、OS 標準の日本語フォントを使用します。')
    ).toBeInTheDocument();
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
      SetupStep.FONT_INSTALLATION,
      'font-download',
      true
    );
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
      SetupStep.FONT_INSTALLATION,
      'font-place',
      true
    );
    expect(screen.queryByRole('button', { name: /ダウンロードページ/ })).not.toBeInTheDocument();
  });

  it('keeps the custom font route when ikamodoki1.ttf is available', async () => {
    mocks.checkSystem.mockResolvedValue({
      is_installed: true,
      installation_path: 'C:\\SplatReplay\\assets\\thumbnail\\ikamodoki1.ttf',
    });

    render(FontInstallation);

    expect(await screen.findByText('ikamodoki1.ttf を使用できます。')).toBeInTheDocument();
    expect(screen.getByText('イカモドキを使用')).toBeInTheDocument();
  });

  it('shows an unavailable font as a failure and allows a recheck', async () => {
    const user = userEvent.setup();
    render(FontInstallation);

    expect(await screen.findByText(/利用可能な日本語フォントがありません/)).toBeInTheDocument();
    expect(mocks.markSubstepCompleted).toHaveBeenCalledWith(
      SetupStep.FONT_INSTALLATION,
      'font-place',
      false
    );

    await user.click(screen.getByRole('button', { name: 'インストール状態を再確認' }));
    expect(mocks.checkSystem).toHaveBeenCalledTimes(2);
  });
});
