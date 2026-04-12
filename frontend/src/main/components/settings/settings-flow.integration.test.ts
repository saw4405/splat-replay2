/**
 * Settings フロー Integration テスト
 *
 * 責務：
 * - SettingsDialog の統合動作検証
 * - 設定読み込み→セクション切り替え→フィールド編集→保存の一連の流れ
 * - エラーハンドリング
 *
 * 分類: integration
 */

import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import SettingsDialog from './SettingsDialog.svelte';
import type { SettingsResponse } from './types';

describe('Settings フロー Integration', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  const mockSettingsResponse: SettingsResponse = {
    sections: [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'app.debug_mode',
            label: 'デバッグモード',
            description: 'デバッグモードの説明',
            type: 'boolean',
            recommended: false,
            value: false,
            user_editable: true,
          },
          {
            id: 'app.log_level',
            label: 'ログレベル',
            description: 'ログレベルの説明',
            type: 'select',
            recommended: false,
            value: 'info',
            choices: ['debug', 'info', 'error'],
            user_editable: true,
          },
        ],
      },
      {
        id: 'recording',
        label: '録画設定',
        fields: [
          {
            id: 'recording.quality',
            label: '録画品質',
            description: '録画品質の説明',
            type: 'select',
            recommended: false,
            value: 'high',
            choices: ['low', 'medium', 'high'],
            user_editable: true,
          },
        ],
      },
    ],
  };

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
    delete document.documentElement.dataset.renderMode;

    // デフォルトの設定取得レスポンス
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(mockSettingsResponse), { status: 200 })
    );
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.restoreAllMocks();
    delete document.documentElement.dataset.renderMode;
  });

  describe('初期化と設定読み込み', () => {
    it('ダイアログを開くと設定が読み込まれる', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith('/api/settings', { cache: 'no-store' });
      });
    });

    it('設定読み込み成功時にセクションが表示される', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('一般設定')).toBeInTheDocument();
        expect(screen.queryByText('録画設定')).toBeInTheDocument();
      });
    });

    it('最初のセクションがアクティブになる', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });
    });

    it('設定読み込み失敗時にエラーメッセージが表示される', async () => {
      fetchMock.mockResolvedValue(new Response('{}', { status: 500 }));

      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText(/failed with status 500/)).toBeInTheDocument();
      });
    });
  });

  describe('セクション切り替え', () => {
    it('セクションをクリックすると切り替わる', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('一般設定')).toBeInTheDocument();
      });

      // 録画設定セクションに切り替え
      const recordingSection = screen.getByText('録画設定');
      await fireEvent.click(recordingSection);

      await waitFor(() => {
        expect(screen.queryByText('録画品質')).toBeInTheDocument();
      });
    });

    it('異なるセクション間でフィールドが切り替わる', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      // 一般設定のフィールドが表示されている
      expect(screen.queryByText('デバッグモード')).toBeInTheDocument();

      // 録画設定に切り替え
      const recordingSection = screen.getByText('録画設定');
      await fireEvent.click(recordingSection);

      // 録画設定のフィールドが表示される
      await waitFor(() => {
        expect(screen.queryByText('録画品質')).toBeInTheDocument();
      });

      // 一般設定のフィールドは表示されない
      expect(screen.queryByText('デバッグモード')).not.toBeInTheDocument();
    });
  });

  describe('フィールド編集', () => {
    it('Boolean フィールドの値を変更できる', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);

      await fireEvent.click(checkbox);

      expect(checkbox.checked).toBe(true);
    });

    it('Select フィールドの値を変更できる', async () => {
      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('ログレベル')).toBeInTheDocument();
      });

      // SelectFieldはカスタムコンポーネント（button）なので、値を含むspan要素を確認
      const selectButton = screen.getByRole('combobox');
      let selectValueSpan = selectButton.querySelector('.select-value');
      expect(selectValueSpan?.textContent).toBe('info');

      // SelectFieldはクリックしてドロップダウンを開く
      await fireEvent.click(selectButton);

      // ドロップダウンが開いてオプションが表示されるまで待つ
      await waitFor(() => {
        const listbox = screen.getByRole('listbox');
        expect(listbox).toBeInTheDocument();
      });

      // 'error'オプションを探す（listbox内の全てのoptionから）
      const errorOption = await waitFor(() => {
        const options = screen.getAllByRole('option');
        const errorOpt = options.find((opt) => opt.textContent?.includes('error'));
        expect(errorOpt).toBeDefined();
        return errorOpt!;
      });

      // オプションをmousedownで選択（SelectFieldはmousedownを使用）
      await fireEvent.mouseDown(errorOption);

      // 値が更新されるまで待つ（ドロップダウンが閉じるのを待つ）
      await waitFor(
        () => {
          selectValueSpan = selectButton.querySelector('.select-value');
          expect(selectValueSpan?.textContent).toBe('error');
        },
        { timeout: 2000 }
      );
    });
  });

  describe('保存フロー', () => {
    it('保存ボタンをクリックすると設定が送信される', async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(mockSettingsResponse), { status: 200 })
      );
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }));

      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: '保存' });
      await fireEvent.click(saveButton);

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/settings',
          expect.objectContaining({
            method: 'PUT',
          })
        );
      });
    });

    it('保存成功時にダイアログが閉じる', async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(mockSettingsResponse), { status: 200 })
      );
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }));

      const { component } = render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: '保存' });
      await fireEvent.click(saveButton);

      await waitFor(() => {
        expect(component.open).toBe(false);
      });
    });

    it('GPU を選んで保存すると raw 値 gpu を送信してダイアログを閉じる', async () => {
      const webviewSettingsResponse: SettingsResponse = {
        sections: [
          {
            id: 'webview',
            label: '表示',
            fields: [
              {
                id: 'render_mode',
                label: '描画モード',
                description:
                  'CPU: プレビュー表示はややカクつきますが、OBSの録画は安定しやすい設定です。 ' +
                  'GPU: プレビュー表示は滑らかですが、GPU負荷が高くなり、OBSの録画結果に影響する場合があります。 ' +
                  'プレビュー更新頻度の変更は保存後すぐに反映されます。 ' +
                  '描画モードの切り替えは再起動後に反映されます。',
                type: 'select',
                recommended: false,
                value: 'cpu',
                choices: ['cpu', 'gpu'],
                choice_labels: { cpu: 'CPU', gpu: 'GPU' },
                user_editable: true,
              },
            ],
          },
        ],
      };

      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(webviewSettingsResponse), { status: 200 })
      );
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }));

      const { component } = render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.getByTestId('settings-section-display')).toHaveTextContent('表示');
        expect(screen.queryByText('描画モード')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('settings-section-webview')).not.toBeInTheDocument();

      await fireEvent.click(screen.getByRole('combobox'));

      await waitFor(() => {
        expect(screen.getByRole('option', { name: 'GPU' })).toBeInTheDocument();
      });

      await fireEvent.mouseDown(screen.getByRole('option', { name: 'GPU' }));
      await fireEvent.click(screen.getByRole('button', { name: '保存' }));

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/settings',
          expect.objectContaining({
            method: 'PUT',
            body: JSON.stringify({
              sections: [
                {
                  id: 'webview',
                  values: { render_mode: 'gpu' },
                },
              ],
            }),
          })
        );
      });

      await waitFor(() => {
        expect(component.open).toBe(false);
      });

      expect(document.documentElement.dataset.renderMode).toBe('gpu');
    });

    it('保存失敗時にエラーメッセージが表示される', async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(mockSettingsResponse), { status: 200 })
      );
      fetchMock.mockResolvedValueOnce(new Response('{}', { status: 500 }));

      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: '保存' });
      await fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.queryByText(/failed with status 500/)).toBeInTheDocument();
      });
    });
  });

  describe('キャンセルフロー', () => {
    it('キャンセルボタンをクリックするとダイアログが閉じる', async () => {
      const { component } = render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: 'キャンセル' });
      await fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(component.open).toBe(false);
      });
    });
  });

  describe('再表示時の動作', () => {
    it('ダイアログを閉じて再度開くと設定が再読み込みされる', async () => {
      const { rerender } = render(SettingsDialog, { props: { open: true } });

      // 初回の読み込みを待つ
      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(screen.queryByText('デバッグモード')).toBeInTheDocument();
      });

      // 閉じる（resetStateが実行され、sectionsが空になる）
      await rerender({ open: false });

      // fetchMockに追加のレスポンスを設定
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(mockSettingsResponse), { status: 200 })
      );

      // 再度開く（sections.length === 0なので再読み込みされるはず）
      await rerender({ open: true });

      // 2回目の読み込みを待つ
      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('user_editable フィルタリング', () => {
    it('user_editable=false のフィールドは表示されない', async () => {
      const responseWithNonEditable: SettingsResponse = {
        sections: [
          {
            id: 'test',
            label: 'テスト',
            fields: [
              {
                id: 'editable',
                label: '編集可能',
                description: '編集可能フィールドの説明',
                type: 'boolean',
                recommended: false,
                value: true,
                user_editable: true,
              },
              {
                id: 'non_editable',
                label: '編集不可',
                description: '編集不可フィールドの説明',
                type: 'boolean',
                recommended: false,
                value: false,
                user_editable: false,
              },
            ],
          },
        ],
      };

      fetchMock.mockResolvedValue(
        new Response(JSON.stringify(responseWithNonEditable), { status: 200 })
      );

      render(SettingsDialog, { props: { open: true } });

      await waitFor(() => {
        expect(screen.queryByText('編集可能')).toBeInTheDocument();
      });

      expect(screen.queryByText('編集不可')).not.toBeInTheDocument();
    });
  });
});
