import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import ErrorDialog from './ErrorDialog.svelte';
import type { ApiError } from '../types';

describe('ErrorDialog', () => {
  describe('ダイアログ表示', () => {
    it('openがtrueの場合、エラーダイアログが表示される', () => {
      render(ErrorDialog, {
        props: {
          open: true,
          message: 'テストエラーメッセージ',
        },
      });

      expect(screen.queryByText('テストエラーメッセージ')).toBeInTheDocument();
    });

    it('openがfalseの場合、ダイアログが表示されない', () => {
      render(ErrorDialog, {
        props: {
          open: false,
          message: 'テストエラーメッセージ',
        },
      });

      expect(screen.queryByText('テストエラーメッセージ')).not.toBeInTheDocument();
    });

    it('カスタムタイトルが表示される', () => {
      render(ErrorDialog, {
        props: {
          open: true,
          title: 'カスタムエラータイトル',
          message: 'エラー内容',
        },
      });

      expect(screen.queryByText('カスタムエラータイトル')).toBeInTheDocument();
    });
  });

  describe('ApiErrorオブジェクト', () => {
    it('ApiErrorのerrorプロパティが表示される', () => {
      const apiError: ApiError = {
        error: 'API エラーメッセージ',
      };

      render(ErrorDialog, {
        props: {
          open: true,
          error: apiError,
        },
      });

      expect(screen.queryByText('API エラーメッセージ')).toBeInTheDocument();
    });

    it('エラーコードが表示される', () => {
      const apiError: ApiError = {
        error: 'エラー内容',
        error_code: 'ERR_001',
      };

      render(ErrorDialog, {
        props: {
          open: true,
          error: apiError,
        },
      });

      expect(screen.queryByText('エラーコード: ERR_001')).toBeInTheDocument();
    });

    it('推奨される対処方法が表示される', () => {
      const apiError: ApiError = {
        error: 'エラー内容',
        recovery_action: '設定を確認してください',
      };

      render(ErrorDialog, {
        props: {
          open: true,
          error: apiError,
        },
      });

      expect(screen.queryByText('推奨される対処方法')).toBeInTheDocument();
      expect(screen.queryByText('設定を確認してください')).toBeInTheDocument();
    });
  });

  describe('閉じる処理', () => {
    it('閉じるボタンをクリックするとonCloseコールバックが呼ばれる', async () => {
      const onCloseMock = vi.fn();

      render(ErrorDialog, {
        props: {
          open: true,
          message: 'エラー',
          onClose: onCloseMock,
        },
      });

      const closeButton = screen.getByRole('button', { name: '閉じる' });
      await fireEvent.click(closeButton);

      expect(onCloseMock).toHaveBeenCalledTimes(1);
    });

    it('onCloseが未定義でもエラーが発生しない', async () => {
      render(ErrorDialog, {
        props: {
          open: true,
          message: 'エラー',
        },
      });

      const closeButton = screen.getByRole('button', { name: '閉じる' });
      await fireEvent.click(closeButton);

      // エラーが発生しないことを確認（例外がスローされない）
    });
  });

  describe('再試行処理', () => {
    it('onRetryが指定されている場合、再試行ボタンが表示される', () => {
      const onRetryMock = vi.fn();

      render(ErrorDialog, {
        props: {
          open: true,
          message: 'エラー',
          onRetry: onRetryMock,
        },
      });

      expect(screen.queryByRole('button', { name: '再試行' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '閉じる' })).toBeInTheDocument();
    });

    it('再試行ボタンをクリックするとonRetryコールバックが呼ばれる', async () => {
      const onRetryMock = vi.fn();
      const onCloseMock = vi.fn();

      render(ErrorDialog, {
        props: {
          open: true,
          message: 'エラー',
          onRetry: onRetryMock,
          onClose: onCloseMock,
        },
      });

      const retryButton = screen.getByRole('button', { name: '再試行' });
      await fireEvent.click(retryButton);

      expect(onRetryMock).toHaveBeenCalledTimes(1);
      expect(onCloseMock).toHaveBeenCalledTimes(1);
    });

    it('onRetryが未定義の場合、再試行ボタンではなく閉じるボタンのみ表示される', () => {
      render(ErrorDialog, {
        props: {
          open: true,
          message: 'エラー',
        },
      });

      expect(screen.queryByRole('button', { name: '再試行' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '閉じる' })).toBeInTheDocument();
    });
  });
});
