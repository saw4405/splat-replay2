import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import YouTubePermissionDialog from './YouTubePermissionDialog.svelte';

describe('YouTubePermissionDialog', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('ダイアログ表示', () => {
    it('openがtrueの場合、ダイアログが表示される', () => {
      render(YouTubePermissionDialog, { props: { open: true } });

      expect(screen.queryByText('YouTubeへのアクセス許可')).toBeInTheDocument();
      expect(
        screen.queryByText(/Googleの認証画面が表示された場合、Googleアカウントでログインし/)
      ).toBeInTheDocument();
    });

    it('openがfalseの場合、ダイアログが表示されない', () => {
      render(YouTubePermissionDialog, { props: { open: false } });

      expect(screen.queryByText('YouTubeへのアクセス許可')).not.toBeInTheDocument();
    });
  });

  describe('チェックボックス操作', () => {
    it('「再度表示しない」チェックボックスが表示される', () => {
      render(YouTubePermissionDialog, { props: { open: true } });

      const checkbox = screen.getByRole('checkbox', { name: '再度表示しない' });
      expect(checkbox).toBeInTheDocument();
      expect(checkbox).not.toBeChecked();
    });

    it('チェックボックスをクリックするとチェックが付く', async () => {
      render(YouTubePermissionDialog, { props: { open: true } });

      const checkbox = screen.getByRole('checkbox', { name: '再度表示しない' });
      await fireEvent.click(checkbox);

      expect(checkbox).toBeChecked();
    });
  });

  describe('閉じる処理', () => {
    it('チェックなしで閉じるボタンを押すとfetchが呼ばれない', async () => {
      fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      render(YouTubePermissionDialog, { props: { open: true } });

      const closeButton = screen.getByRole('button', { name: '閉じる' });
      await fireEvent.click(closeButton);

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it('チェック付きで閉じるとfetchが呼ばれる', async () => {
      fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      render(YouTubePermissionDialog, { props: { open: true } });

      const checkbox = screen.getByRole('checkbox', { name: '再度表示しない' });
      await fireEvent.click(checkbox);

      const closeButton = screen.getByRole('button', { name: '閉じる' });
      await fireEvent.click(closeButton);

      expect(fetchMock).toHaveBeenCalledWith('/api/settings/youtube-permission-dialog', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shown: true }),
      });
    });

    it('fetchエラー時もダイアログは閉じる', async () => {
      fetchMock.mockRejectedValue(new Error('Network error'));
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      render(YouTubePermissionDialog, { props: { open: true } });

      const checkbox = screen.getByRole('checkbox', { name: '再度表示しない' });
      await fireEvent.click(checkbox);

      const closeButton = screen.getByRole('button', { name: '閉じる' });
      await fireEvent.click(closeButton);

      expect(fetchMock).toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to save youtube permission dialog state:',
        expect.any(Error)
      );

      consoleErrorSpy.mockRestore();
    });
  });
});
