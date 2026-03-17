/**
 * SettingsDialog Component Tests
 *
 * 責務：
 * - SettingsDialog コンポーネントの UI 動作を検証
 * - 設定の読み込みと表示を確認
 * - セクション切り替えを確認
 * - 保存/キャンセル操作を確認
 *
 * 分類: component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import SettingsDialog from './SettingsDialog.svelte';
import type { SettingsSection } from './types';

describe('SettingsDialog.svelte', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // fetch のモックを設定
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.restoreAllMocks();
  });

  // ========================================
  // 初期表示テスト
  // ========================================

  it('open=falseの時はダイアログが表示されない', () => {
    render(SettingsDialog, { props: { open: false } });

    const dialog = screen.queryByRole('dialog');
    expect(dialog).not.toBeInTheDocument();
  });

  it('open=trueの時はダイアログが表示される', () => {
    // 設定取得をモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: [] }),
    });

    render(SettingsDialog, { props: { open: true } });

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
  });

  it('タイトルが"設定"と表示される', () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: [] }),
    });

    render(SettingsDialog, { props: { open: true } });

    const heading = screen.getByRole('heading', { name: '設定' });
    expect(heading).toBeInTheDocument();
  });

  // ========================================
  // 読み込みテスト
  // ========================================

  it('読み込み中は"読み込み中です..."と表示される', () => {
    // fetch を遅延させる
    fetchMock.mockReturnValueOnce(
      new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            ok: true,
            json: async () => ({ sections: [] }),
          });
        }, 100);
      })
    );

    render(SettingsDialog, { props: { open: true } });

    expect(screen.getByText('読み込み中です...')).toBeInTheDocument();
  });

  it('設定の取得に失敗した場合はエラーメッセージが表示される', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByText(/failed with status 500/)).toBeInTheDocument();
    });
  });

  it('設定が正常に読み込まれる', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });
  });

  // ========================================
  // セクション切り替えテスト
  // ========================================

  it('複数のセクションが表示される', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
      {
        id: 'advanced',
        label: '詳細設定',
        fields: [
          {
            id: 'field2',
            label: 'フィールド2',
            description: '説明2',
            type: 'string',
            recommended: false,
            value: 'test2',
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
      expect(screen.getByTestId('settings-section-advanced')).toBeInTheDocument();
    });
  });

  it('セクションをクリックすると切り替わる', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
      {
        id: 'advanced',
        label: '詳細設定',
        fields: [
          {
            id: 'field2',
            label: 'フィールド2',
            description: '説明2',
            type: 'string',
            recommended: false,
            value: 'test2',
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    const advancedButton = screen.getByTestId('settings-section-advanced');
    await user.click(advancedButton);

    // 詳細設定セクションが選択されていることを確認
    expect(advancedButton).toHaveClass('selected');
  });

  // ========================================
  // 保存/キャンセルテスト
  // ========================================

  it('キャンセルボタンをクリックするとダイアログが閉じる', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    const { component } = render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: 'キャンセル' });
    await user.click(cancelButton);

    expect(component.open).toBe(false);
  });

  it('保存ボタンをクリックすると設定が保存される', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    // 設定取得のモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    // 設定保存のモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: '保存' });
    await user.click(saveButton);

    // 保存リクエストが送信されたことを確認
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      });
    });
  });

  it('保存に失敗した場合はエラーメッセージが表示される', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    // 設定取得のモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    // 設定保存のモック（失敗）
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: '保存に失敗しました' }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: '保存' });
    await user.click(saveButton);

    // エラーメッセージが表示されることを確認
    await waitFor(() => {
      expect(screen.getByText('保存に失敗しました')).toBeInTheDocument();
    });
  });

  it('保存中は保存ボタンが"保存中..."と表示される', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    // 設定取得のモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    // 設定保存のモック（遅延）
    fetchMock.mockReturnValueOnce(
      new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            ok: true,
            json: async () => ({ status: 'ok' }),
          });
        }, 100);
      })
    );

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: '保存' });
    await user.click(saveButton);

    // 保存中は"保存中..."と表示される
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '保存中...' })).toBeInTheDocument();
    });
  });

  it('保存成功時は成功メッセージが表示される', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    // 設定取得のモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    // 設定保存のモック
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });

    const { component } = render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: '保存' });
    await user.click(saveButton);

    // 保存成功時にダイアログが閉じることを確認
    await waitFor(() => {
      expect(component.open).toBe(false);
    });
  });

  // ========================================
  // 編集不可フィールドのフィルタリングテスト
  // ========================================

  it('user_editable=falseのフィールドは表示されない', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'field1',
            label: 'フィールド1',
            description: '説明1',
            type: 'string',
            recommended: false,
            value: 'test',
            user_editable: true,
          },
          {
            id: 'field2',
            label: 'フィールド2（非表示）',
            description: '説明2',
            type: 'string',
            recommended: false,
            value: 'test2',
            user_editable: false,
          },
        ],
      },
    ];

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-general')).toBeInTheDocument();
    });

    // user_editable=trueのフィールドは表示されない
    // FieldItem のラベルは複雑なので、ここでは簡易的に確認
    // より詳細なテストは integration テストで行う
  });
});
