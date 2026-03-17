import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import ConfirmDialog from './ConfirmDialog.svelte';

describe('ConfirmDialog.svelte (integration)', () => {
  it('message が表示される', () => {
    render(ConfirmDialog, {
      props: {
        isOpen: true,
        message: '本当に削除しますか？',
      },
    });

    expect(screen.getByText('本当に削除しますか？')).toBeInTheDocument();
  });

  it('確認ボタンをクリックすると confirm イベントが発火し、ダイアログが閉じる', async () => {
    const user = userEvent.setup();
    const mockConfirm = vi.fn();

    const { component } = render(ConfirmDialog, {
      props: {
        isOpen: true,
        message: 'テストメッセージ',
        confirmText: '確認',
      },
    });

    component.$on('confirm', mockConfirm);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    const confirmButton = screen.getByRole('button', { name: '確認' });
    await user.click(confirmButton);

    // イベントは同期的に発火されるが、DOMの更新は非同期のため waitFor を使用
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    expect(mockConfirm).toHaveBeenCalledTimes(1);
  });

  it('キャンセルボタンをクリックすると cancel イベントが発火し、ダイアログが閉じる', async () => {
    const user = userEvent.setup();
    const mockCancel = vi.fn();

    const { component } = render(ConfirmDialog, {
      props: {
        isOpen: true,
        message: 'テストメッセージ',
        cancelText: 'やめる',
      },
    });

    component.$on('cancel', mockCancel);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    const cancelButton = screen.getByRole('button', { name: 'やめる' });
    await user.click(cancelButton);

    // イベントは同期的に発火されるが、DOMの更新は非同期のため waitFor を使用
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    expect(mockCancel).toHaveBeenCalledTimes(1);
  });

  it('BaseDialog のタイトルが「確認」と表示される', () => {
    render(ConfirmDialog, {
      props: {
        isOpen: true,
        message: 'テスト',
      },
    });

    const heading = screen.getByRole('heading', { name: '確認' });
    expect(heading).toBeInTheDocument();
  });

  it('カスタムボタンテキストが反映される', () => {
    render(ConfirmDialog, {
      props: {
        isOpen: true,
        message: 'テスト',
        confirmText: '実行',
        cancelText: '中止',
      },
    });

    expect(screen.getByRole('button', { name: '実行' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '中止' })).toBeInTheDocument();
  });

  it('複数行のメッセージが表示される', () => {
    const multiLineMessage = '1行目\n2行目\n3行目';

    render(ConfirmDialog, {
      props: {
        isOpen: true,
        message: multiLineMessage,
      },
    });

    // 各行が表示されることを確認
    expect(screen.getByText(/1行目/)).toBeInTheDocument();
    expect(screen.getByText(/2行目/)).toBeInTheDocument();
    expect(screen.getByText(/3行目/)).toBeInTheDocument();
  });
});
