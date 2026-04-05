import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import BaseDialog from './BaseDialog.svelte';

describe('BaseDialog.svelte', () => {
  it('open が true の時にダイアログが表示される', () => {
    render(BaseDialog, { props: { open: true, title: 'テストダイアログ' } });

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
  });

  it('open が false の時にダイアログが表示されない', () => {
    render(BaseDialog, { props: { open: false, title: 'テストダイアログ' } });

    const dialog = screen.queryByRole('dialog');
    expect(dialog).not.toBeInTheDocument();
  });

  it('title prop が見出しに表示される', () => {
    render(BaseDialog, { props: { open: true, title: 'テストタイトル' } });

    const heading = screen.getByRole('heading', { name: 'テストタイトル' });
    expect(heading).toBeInTheDocument();
  });

  it('プライマリボタンをクリックすると onPrimaryClick が呼ばれる', async () => {
    const user = userEvent.setup();
    const mockPrimaryClick = vi.fn();

    render(BaseDialog, {
      props: {
        open: true,
        title: 'テスト',
        primaryButtonText: '保存',
        onPrimaryClick: mockPrimaryClick,
      },
    });

    const primaryButton = screen.getByRole('button', { name: '保存' });
    await user.click(primaryButton);

    expect(mockPrimaryClick).toHaveBeenCalledTimes(1);
  });

  it('セカンダリボタンをクリックすると onSecondaryClick が呼ばれる', async () => {
    const user = userEvent.setup();
    const mockSecondaryClick = vi.fn();

    render(BaseDialog, {
      props: {
        open: true,
        title: 'テスト',
        secondaryButtonText: 'キャンセル',
        onSecondaryClick: mockSecondaryClick,
      },
    });

    const secondaryButton = screen.getByRole('button', { name: 'キャンセル' });
    await user.click(secondaryButton);

    expect(mockSecondaryClick).toHaveBeenCalledTimes(1);
  });

  it('Escape キーでダイアログが閉じる（allowBackdropClose が true の時）', async () => {
    const user = userEvent.setup();

    render(BaseDialog, {
      props: { open: true, title: 'テスト', allowBackdropClose: true },
    });

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('Escape キーでダイアログが閉じない（allowBackdropClose が false の時）', async () => {
    const user = userEvent.setup();

    render(BaseDialog, {
      props: { open: true, title: 'テスト', allowBackdropClose: false },
    });

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('showHeader が false の時にヘッダーが表示されない', () => {
    render(BaseDialog, { props: { open: true, title: 'テスト', showHeader: false } });

    const heading = screen.queryByRole('heading');
    expect(heading).not.toBeInTheDocument();
  });

  it('showFooter が false の時にフッターが表示されない', () => {
    render(BaseDialog, { props: { open: true, title: 'テスト', showFooter: false } });

    const primaryButton = screen.queryByRole('button', { name: '保存' });
    const secondaryButton = screen.queryByRole('button', { name: 'キャンセル' });

    expect(primaryButton).not.toBeInTheDocument();
    expect(secondaryButton).not.toBeInTheDocument();
  });

  it('disablePrimaryButton が true の時にプライマリボタンが無効化される', () => {
    render(BaseDialog, {
      props: { open: true, title: 'テスト', disablePrimaryButton: true },
    });

    const primaryButton = screen.getByRole('button', { name: '保存' });
    expect(primaryButton).toBeDisabled();
  });
});
