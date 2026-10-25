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
import { render, screen, waitFor, cleanup, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import SettingsDialog from './SettingsDialog.svelte';
import type { SetupPlatform } from '../../../setup/platform';
import type { SettingsSection } from './types';

const setupPlatformMock = vi.hoisted(() => vi.fn((): SetupPlatform => 'windows'));
vi.mock('../../../setup/platform', () => ({ getSetupPlatform: setupPlatformMock }));

describe('SettingsDialog.svelte', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // fetch のモックを設定
    fetchMock = vi.fn();
    global.fetch = fetchMock;
    setupPlatformMock.mockReturnValue('windows');
    delete document.documentElement.dataset.renderMode;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    delete document.documentElement.dataset.renderMode;
  });

  it('基本設定と全設定の切替で外部送信説明を一度だけ表示する', async () => {
    const user = userEvent.setup();
    const sections: SettingsSection[] = [
      {
        id: 'speech_transcriber',
        label: '文字起こし',
        fields: [
          {
            id: 'enabled',
            label: '文字起こしを有効にする',
            description: '',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            user_editable: true,
            value: false,
          },
        ],
      },
    ];
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ sections }) });
    render(SettingsDialog, { props: { open: true } });
    const summary = '送信されるデータとログの保存場所';
    expect(await screen.findAllByText(summary)).toHaveLength(1);
    await user.click(screen.getByText(summary));
    expect(screen.getByText(/Google 音声認識と Groq Whisper/)).toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: 'すべての設定', exact: true }));
    await user.click(screen.getByTestId('settings-section-recording'));
    expect(screen.getAllByText(summary)).toHaveLength(1);
    await user.click(screen.getByRole('radio', { name: '基本設定', exact: true }));
    expect(screen.getAllByText(summary)).toHaveLength(1);
  });

  // ========================================
  // 初期表示テスト
  // ========================================

  it('保存区分に保持トグルと保存先を表示し現在値を保存する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'storage',
        label: '動画保存',
        fields: [
          {
            id: 'keep_recordings_after_edit',
            label: '編集後も元録画を保持',
            description: 'オン: 保持 / オフ: 削除。保管先: /videos/retained/recorded',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: false,
            user_editable: true,
          },
          {
            id: 'keep_edited_after_upload',
            label: 'アップロード後も編集済み動画を保持',
            description: 'オン: 保持 / オフ: 削除。保管先: /videos/retained/edited',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: false,
            user_editable: true,
          },
        ],
      },
    ];
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    render(SettingsDialog, { props: { open: true } });

    await user.click(await screen.findByRole('radio', { name: 'すべての設定' }));
    await user.click(await screen.findByTestId('settings-section-storage'));
    const recordedField = screen.getByTestId(
      'settings-field-storage-storage-keep_recordings_after_edit'
    );
    const editedField = screen.getByTestId(
      'settings-field-storage-storage-keep_edited_after_upload'
    );
    const recordedCheckbox = within(recordedField).getByRole('checkbox', {
      name: '編集後も元録画を保持',
    });
    const editedCheckbox = within(editedField).getByRole('checkbox', {
      name: 'アップロード後も編集済み動画を保持',
    });

    expect(recordedCheckbox).not.toBeChecked();
    expect(editedCheckbox).not.toBeChecked();
    expect(recordedField).toHaveTextContent('オン: 保持 / オフ: 削除');
    expect(recordedField).toHaveTextContent('/videos/retained/recorded');
    expect(editedField).toHaveTextContent('/videos/retained/edited');

    await user.click(recordedCheckbox);
    await user.click(editedCheckbox);
    await user.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '設定' })).not.toBeInTheDocument();
    });
    const updateCall = fetchMock.mock.calls.find(
      ([url, options]) => url === '/api/settings' && options?.method === 'PUT'
    );
    expect(updateCall).toBeDefined();
    const updatePayload = JSON.parse(updateCall?.[1]?.body as string) as {
      sections: Array<{ id: string; values: Record<string, boolean> }>;
    };
    expect(updatePayload.sections).toContainEqual({
      id: 'storage',
      values: {
        keep_recordings_after_edit: true,
        keep_edited_after_upload: true,
      },
    });
  });

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

  it('タイトル行の切替は基本設定を初期選択し、すべての設定で追加項目を表示する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'required_field',
            label: '必須項目',
            description: '',
            type: 'string',
            requirement: 'required',
            display_level: 'basic',
            value: '基本値',
            user_editable: true,
          },
          {
            id: 'advanced_field',
            label: '詳細項目',
            description: '',
            type: 'string',
            requirement: 'optional',
            display_level: 'advanced',
            value: '詳細値',
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

    const displayModeGroup = screen.getByRole('group', { name: '設定項目の表示範囲' });
    const basicRadio = within(displayModeGroup).getByRole('radio', { name: '基本設定' });
    const allRadio = within(displayModeGroup).getByRole('radio', { name: 'すべての設定' });
    await waitFor(() => {
      expect(screen.getByRole('textbox', { name: '必須項目 必須' })).toBeInTheDocument();
    });

    expect(basicRadio).toBeChecked();
    expect(screen.queryByRole('textbox', { name: '詳細項目' })).not.toBeInTheDocument();

    await user.click(allRadio);

    expect(allRadio).toBeChecked();
    expect(screen.getByRole('textbox', { name: '必須項目 必須' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: '詳細項目' })).toBeInTheDocument();
  });

  it('基本設定がないタブからすべての設定へ切り替えられる', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [
          {
            id: 'advanced_field',
            label: '詳細項目',
            description: '',
            type: 'string',
            requirement: 'optional',
            display_level: 'advanced',
            value: '詳細値',
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

    const showAllButton = await screen.findByRole('button', { name: 'すべての設定を表示' });
    expect(screen.getByText('基本設定に表示する項目はありません。')).toBeInTheDocument();

    await user.click(showAllButton);

    expect(screen.getByRole('radio', { name: 'すべての設定' })).toBeChecked();
    expect(screen.getByRole('textbox', { name: '詳細項目' })).toBeInTheDocument();
  });

  // ========================================
  // 読み込みテスト
  // ========================================

  it('読み込み中は進行中と分かるインジケーターと文言を表示する', () => {
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

    const loadingStatus = screen.getByRole('status');
    expect(loadingStatus).toHaveTextContent('読み込み中です...');
    expect(screen.getByTestId('settings-loading-spinner')).toBeInTheDocument();
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
            requirement: 'optional',
            display_level: 'basic',
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

  it('LAN 公開が有効でも未反映の場合はURL候補を開けるものとして表示しない', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'webview',
        label: '表示',
        fields: [
          {
            id: 'render_mode',
            label: '描画モード',
            description: '',
            type: 'select',
            requirement: 'optional',
            display_level: 'basic',
            value: 'gpu',
            choices: ['cpu', 'gpu'],
            user_editable: true,
          },
        ],
      },
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            active: false,
            bind_host: '127.0.0.1',
            port: 8000,
            restart_required: true,
            access_urls: ['http://192.168.1.20:8000/'],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    let summary: HTMLElement | null = null;
    await waitFor(() => {
      summary = screen.getByTestId('remote-access-summary');
      expect(summary).toBeInTheDocument();
    });
    const summaryQueries = within(summary as HTMLElement);
    expect(summaryQueries.getByText('LAN 公開')).toBeInTheDocument();
    expect(summaryQueries.getByText('有効')).toBeInTheDocument();
    expect(summaryQueries.queryByText('http://192.168.1.20:8000/')).not.toBeInTheDocument();
    expect(summaryQueries.getByText('変更はアプリ再起動後に反映されます。')).toBeInTheDocument();
  });

  it('LAN 公開の変更が未保存なら保存と再起動を案内する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: false,
            user_editable: true,
          },
        ],
      },
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input) === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: false,
            active: false,
            bind_host: '127.0.0.1',
            port: 8000,
            restart_required: false,
            access_urls: [],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ sections: mockSections }) });
    });

    render(SettingsDialog, { props: { open: true } });
    await user.click(await screen.findByRole('checkbox', { name: 'LAN 公開' }));

    const summary = await screen.findByTestId('remote-access-summary');
    await waitFor(() => {
      expect(within(summary).getByText('未保存')).toBeInTheDocument();
    });
    expect(
      within(summary).getByText('「保存」を押してアプリを再起動するとURL候補を表示します。')
    ).toBeInTheDocument();
    expect(
      within(summary).queryByText('初期状態ではPC内からのみ接続できます。')
    ).not.toBeInTheDocument();
  });

  it('LAN 公開がOFFの場合はLAN公開サマリーと手順を表示しない', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: false,
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ sections: mockSections }),
    });

    render(SettingsDialog, { props: { open: true } });

    await waitFor(() => {
      expect(
        screen.getByTestId('settings-field-display-remote_access-enabled')
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId('remote-access-summary')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Wi-Fiをプライベートネットワークに設定してください。')
    ).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith('/api/remote-access/status', {
      cache: 'no-store',
    });
  });

  it('表示タブはsource区分を見出しにせず設定項目のラベルを直接表示する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'webview',
        label: '表示',
        fields: [
          {
            id: 'render_mode',
            label: '描画モード',
            description: '',
            type: 'select',
            requirement: 'optional',
            display_level: 'basic',
            value: 'gpu',
            choices: ['cpu', 'gpu'],
            choice_labels: { cpu: 'CPU', gpu: 'GPU' },
            user_editable: true,
          },
        ],
      },
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: false,
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

    await user.click(screen.getByRole('radio', { name: 'すべての設定' }));
    const panel = await screen.findByRole('tabpanel');
    expect(within(panel).getByRole('combobox', { name: '描画モード' })).toBeInTheDocument();
    expect(within(panel).getByRole('checkbox', { name: 'LAN 公開' })).toBeInTheDocument();
    expect(within(panel).queryByRole('group', { name: '表示' })).not.toBeInTheDocument();
    expect(within(panel).queryByRole('group', { name: 'LAN 公開' })).not.toBeInTheDocument();
  });

  it.each([8000, 5173, 8123])('Windows 案内は稼働中の LAN ポート %i を使う', async (port) => {
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            active: true,
            bind_host: '0.0.0.0',
            port,
            restart_required: false,
            access_urls: [`http://192.168.1.20:${port}/`],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    let summary: HTMLElement | null = null;
    await waitFor(() => {
      summary = screen.getByTestId('remote-access-summary');
      expect(summary).toBeInTheDocument();
    });
    expect(screen.queryByRole('group', { name: 'LAN 公開' })).not.toBeInTheDocument();
    const summaryQueries = within(summary as HTMLElement);
    expect(summaryQueries.getByText(`http://192.168.1.20:${port}/`)).toBeInTheDocument();
    expect(
      summaryQueries.getByText('URL候補を別の端末で開いて、LAN接続を確認してください。')
    ).toBeInTheDocument();
    expect(
      summaryQueries.getByText('Wi-Fiをプライベートネットワークに設定してください。')
    ).toBeInTheDocument();
    expect(
      summaryQueries.getByText('Wi-Fiをプライベートネットワークに設定してください。').parentElement
    ).toHaveStyle({ textAlign: 'left' });
    const firewallCommand = summaryQueries.getByText((text) =>
      text.startsWith('New-NetFirewallRule')
    );
    expect(firewallCommand.textContent).toBe(
      [
        'New-NetFirewallRule `',
        `  -DisplayName "Allow TCP ${port} Inbound from LocalSubnet" ` + '`',
        '  -Direction Inbound `',
        '  -Action Allow `',
        '  -Protocol TCP `',
        `  -LocalPort ${port} ` + '`',
        '  -RemoteAddress LocalSubnet',
      ].join('\n')
    );
  });

  it.each([
    { label: '欠落', fields: {} },
    { label: '文字列', fields: { port: '8000' } },
    { label: '0', fields: { port: 0 } },
    { label: '65536', fields: { port: 65536 } },
    { label: '小数', fields: { port: 1.5 } },
  ])('無効な LAN ポートはURLやPowerShellコマンドに表示しない（$label）', async ({ fields }) => {
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input) === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            active: true,
            bind_host: '0.0.0.0',
            ...fields,
            restart_required: false,
            access_urls: ['http://192.168.1.20:8000/'],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    const summary = await screen.findByTestId('remote-access-summary');
    const summaryQueries = within(summary);
    expect(summaryQueries.getByText(/LAN のポート情報を取得できません/)).toBeInTheDocument();
    expect(summaryQueries.queryByText(/New-NetFirewallRule|8000|5173/)).not.toBeInTheDocument();
  });

  it('LAN 状態取得に失敗した場合は具体的なポートやコマンドを表示しない', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input) === '/api/remote-access/status') {
        return Promise.reject(new Error('LAN status unavailable'));
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    const summary = await screen.findByTestId('remote-access-summary');
    const summaryQueries = within(summary);
    expect(summaryQueries.getByText(/LAN のポート情報を取得できません/)).toBeInTheDocument();
    expect(summaryQueries.queryByText(/New-NetFirewallRule|8000|5173/)).not.toBeInTheDocument();
  });

  it('macOS はシステム設定を案内し、Windows 専用のファイアウォール手順を表示しない', async () => {
    setupPlatformMock.mockReturnValue('macos');
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input) === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            active: true,
            bind_host: '0.0.0.0',
            port: 8000,
            restart_required: false,
            access_urls: ['http://192.168.1.20:8000/'],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    const summary = await screen.findByTestId('remote-access-summary');
    const summaryQueries = within(summary);
    expect(summaryQueries.getByText('http://192.168.1.20:8000/')).toBeInTheDocument();
    expect(
      summaryQueries.getByText('URL候補を別の端末で開いて、LAN接続を確認してください。')
    ).toBeInTheDocument();
    expect(
      summaryQueries.getByText(/「ネットワーク」>「ファイアウォール」で SplatReplay\.app/)
    ).toBeInTheDocument();
    expect(
      summaryQueries.getByText(
        /「プライバシーとセキュリティ」>「ローカルネットワーク」に Splat Replay が表示された場合は許可します。項目がない場合は、LAN接続を試した後にもう一度確認してください。/
      )
    ).toBeInTheDocument();
    expect(
      summaryQueries.getByText('アプリがファイアウォール設定を自動変更することはありません。')
    ).toBeInTheDocument();
    expect(
      summaryQueries.queryByText(/PowerShell|New-NetFirewallRule|Windows Firewall/)
    ).not.toBeInTheDocument();
  });

  it('server OS がunknownの場合はOS固有手順を出さず共通のLAN案内を表示する', async () => {
    setupPlatformMock.mockReturnValue('unknown');
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input) === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            active: true,
            bind_host: '0.0.0.0',
            port: 8000,
            restart_required: false,
            access_urls: [],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    const summary = await screen.findByTestId('remote-access-summary');
    const summaryQueries = within(summary);
    expect(
      summaryQueries.getByText(
        'アプリが動作するPCのネットワーク設定と、受信接続の許可を確認してください。'
      )
    ).toBeInTheDocument();
    expect(
      summaryQueries.queryByText(/PowerShell|New-NetFirewallRule|macOS|Windows Firewall/)
    ).not.toBeInTheDocument();
  });

  it('LAN 公開が反映済みでも到達可能URLがない場合は接続可能とは表示しない', async () => {
    const mockSections: SettingsSection[] = [
      {
        id: 'remote_access',
        label: 'LAN アクセス',
        fields: [
          {
            id: 'enabled',
            label: 'LAN 公開',
            description: '家庭内LANからスマホで同じ画面を開けます。',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/remote-access/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            active: true,
            bind_host: '0.0.0.0',
            port: 5173,
            restart_required: false,
            access_urls: [],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

    render(SettingsDialog, { props: { open: true } });

    let summary: HTMLElement | null = null;
    await waitFor(() => {
      summary = screen.getByTestId('remote-access-summary');
      expect(summary).toBeInTheDocument();
    });
    const summaryQueries = within(summary as HTMLElement);
    expect(
      summaryQueries.queryByText('URL候補を別の端末で開いて、LAN接続を確認してください。')
    ).not.toBeInTheDocument();
    expect(
      summaryQueries.getByText('スマホから接続できるLAN URLを確認できません。')
    ).toBeInTheDocument();
  });

  it('choice_labels がある select は表示ラベルを使う', async () => {
    const mockSections = [
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
            requirement: 'optional',
            display_level: 'basic',
            value: 'cpu',
            choices: ['cpu', 'gpu'],
            choice_labels: { cpu: 'CPU', gpu: 'GPU' },
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
      expect(screen.getByText('描画モード')).toBeInTheDocument();
    });

    expect(screen.getByRole('combobox')).toHaveTextContent('CPU');
    expect(
      screen.getByText(/プレビュー更新頻度の変更は保存後すぐに反映されます/)
    ).toBeInTheDocument();
  });

  // ========================================
  // セクション切り替えテスト
  // ========================================

  it('複数のセクションが表示される', async () => {
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
            requirement: 'optional',
            display_level: 'basic',
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
            requirement: 'optional',
            display_level: 'basic',
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

    expect(screen.queryByRole('tablist', { name: '設定カテゴリ' })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: '基本設定' })).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'すべての設定' }));

    const tablist = screen.getByRole('tablist', { name: '設定カテゴリ' });
    const generalTab = within(tablist).getByRole('tab', { name: '一般設定' });
    const advancedTab = within(tablist).getByRole('tab', { name: '詳細設定' });

    expect(generalTab).toHaveAttribute('aria-selected', 'true');
    expect(generalTab).toHaveAttribute('tabindex', '0');
    expect(advancedTab).toHaveAttribute('aria-selected', 'false');
    expect(advancedTab).toHaveAttribute('tabindex', '-1');

    generalTab.focus();
    await user.keyboard('{ArrowRight}');

    expect(advancedTab).toHaveFocus();
    expect(advancedTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', advancedTab.id);
    expect(screen.getByText('フィールド2')).toBeInTheDocument();
  });

  it('既存設定セクションを5つのタブに集約して表示する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'behavior',
        label: '動作',
        fields: [
          {
            id: 'edit_after_power_off',
            label: '電源オフ後に編集開始する',
            description: '',
            type: 'boolean',
            requirement: 'optional',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
      {
        id: 'webview',
        label: '表示',
        fields: [
          {
            id: 'render_mode',
            label: '描画モード',
            description: '',
            type: 'select',
            requirement: 'optional',
            display_level: 'basic',
            value: 'gpu',
            choices: ['cpu', 'gpu'],
            choice_labels: { cpu: 'CPU', gpu: 'GPU' },
            user_editable: true,
          },
        ],
      },
      {
        id: 'capture_device',
        label: 'Capture device settings.',
        fields: [
          {
            id: 'name',
            label: 'キャプチャデバイス名',
            description: '',
            type: 'text',
            requirement: 'required',
            display_level: 'basic',
            value: 'Capture Device',
            user_editable: true,
          },
        ],
      },
      {
        id: 'obs',
        label: 'OBS 接続',
        fields: [
          {
            id: 'websocket_host',
            label: 'OBS WebSocket ホスト',
            description: '',
            type: 'text',
            requirement: 'optional',
            display_level: 'basic',
            value: 'localhost',
            user_editable: true,
          },
        ],
      },
      {
        id: 'speech_transcriber',
        label: '文字起こし',
        fields: [
          {
            id: 'enabled',
            label: '文字起こしを有効にする',
            description: '',
            type: 'boolean',
            requirement: 'required',
            display_level: 'basic',
            value: true,
            user_editable: true,
          },
        ],
      },
      {
        id: 'video_edit',
        label: '動画編集',
        fields: [
          {
            id: 'title_template',
            label: 'タイトルテンプレート',
            description: '',
            type: 'text',
            requirement: 'optional',
            display_level: 'basic',
            value: '{BATTLE}',
            user_editable: true,
          },
        ],
      },
      {
        id: 'upload',
        label: 'アップロード',
        fields: [
          {
            id: 'privacy_status',
            label: '公開範囲',
            description: '',
            type: 'select',
            requirement: 'optional',
            display_level: 'basic',
            value: 'private',
            choices: ['public', 'unlisted', 'private'],
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

    const basicRecordingSection = await screen.findByTestId('settings-section-recording');
    expect(screen.queryByRole('tablist', { name: '設定カテゴリ' })).not.toBeInTheDocument();
    expect(
      within(basicRecordingSection).getByRole('heading', { name: '録画' })
    ).toBeInTheDocument();
    expect(
      within(basicRecordingSection).queryByRole('group', { name: 'キャプチャデバイス' })
    ).not.toBeInTheDocument();
    expect(within(basicRecordingSection).getByText('キャプチャデバイス名')).toBeInTheDocument();
    expect(within(basicRecordingSection).getByText('OBS WebSocket ホスト')).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'すべての設定' }));

    await waitFor(() => {
      expect(screen.getByTestId('settings-section-behavior')).toHaveTextContent('動作');
      expect(screen.getByTestId('settings-section-display')).toHaveTextContent('表示');
      expect(screen.getByTestId('settings-section-recording')).toHaveTextContent('録画');
      expect(screen.getByTestId('settings-section-edit')).toHaveTextContent('編集');
      expect(screen.getByTestId('settings-section-upload')).toHaveTextContent('アップロード');
    });

    expect(screen.queryByTestId('settings-section-capture_device')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-section-obs')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-section-speech_transcriber')).not.toBeInTheDocument();

    await user.click(screen.getByTestId('settings-section-recording'));

    await waitFor(() => {
      expect(
        within(screen.getByRole('group', { name: 'キャプチャデバイス' })).getByRole('heading', {
          name: 'キャプチャデバイス',
        })
      ).toBeInTheDocument();
      expect(
        within(screen.getByRole('group', { name: 'OBS接続' })).getByRole('heading', {
          name: 'OBS接続',
        })
      ).toBeInTheDocument();
      expect(
        within(screen.getByRole('group', { name: '文字起こし' })).getByRole('heading', {
          name: '文字起こし',
        })
      ).toBeInTheDocument();
      expect(screen.getByText('キャプチャデバイス名')).toBeInTheDocument();
      expect(screen.getByText('OBS WebSocket ホスト')).toBeInTheDocument();
      expect(screen.getByText('文字起こしを有効にする')).toBeInTheDocument();
    });
    expect(screen.getAllByText('必須')).toHaveLength(2);
  });

  it('boolean設定は現在状態を可視テキストでも表示する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
      {
        id: 'behavior',
        label: '動作',
        fields: [
          {
            id: 'edit_after_power_off',
            label: '電源オフ後に編集開始する',
            description: '自動処理を開始するかどうか',
            type: 'boolean',
            requirement: 'required',
            display_level: 'basic',
            value: true,
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

    const checkbox = await screen.findByRole('checkbox', {
      name: '電源オフ後に編集開始する 必須',
    });
    expect(screen.getByText('必須')).toBeInTheDocument();
    expect(screen.getByText('オン')).toBeInTheDocument();

    await user.click(checkbox);

    expect(screen.getByText('オフ')).toBeInTheDocument();
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
            requirement: 'optional',
            display_level: 'basic',
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
            requirement: 'optional',
            display_level: 'basic',
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

    await user.click(screen.getByRole('radio', { name: 'すべての設定' }));

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
            requirement: 'optional',
            display_level: 'basic',
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

    const cancelButton = screen.getByRole('button', { name: 'キャンセル' });
    await user.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
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
            requirement: 'optional',
            display_level: 'basic',
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
            requirement: 'optional',
            display_level: 'basic',
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/settings' && init?.method === 'PUT') {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({ detail: '保存に失敗しました' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
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
            requirement: 'optional',
            display_level: 'basic',
            value: 'test',
            user_editable: true,
          },
        ],
      },
    ];

    // 設定保存のモック（明示的に解放するまで保留）
    let resolveSave:
      | ((value: { ok: boolean; json: () => Promise<{ status: string }> }) => void)
      | null = null;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/settings' && init?.method === 'PUT') {
        return new Promise((resolve) => {
          resolveSave = resolve;
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ sections: mockSections }),
      });
    });

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

    resolveSave?.({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('描画モード保存成功時はダイアログを閉じて dataset を即時更新する', async () => {
    const user = userEvent.setup();
    const mockSections: SettingsSection[] = [
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
            requirement: 'optional',
            display_level: 'basic',
            value: 'cpu',
            choices: ['cpu', 'gpu'],
            choice_labels: { cpu: 'CPU', gpu: 'GPU' },
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

    // デバイス選択肢リフレッシュのモック
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
      expect(screen.getByText('描画モード')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('combobox'));
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'GPU' })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('option', { name: 'GPU' }));

    const saveButton = screen.getByRole('button', { name: '保存' });
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    expect(document.documentElement.dataset.renderMode).toBe('gpu');
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
            requirement: 'optional',
            display_level: 'basic',
            value: 'test',
            user_editable: true,
          },
          {
            id: 'field2',
            label: 'フィールド2（非表示）',
            description: '説明2',
            type: 'string',
            requirement: 'optional',
            display_level: 'basic',
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

    expect(screen.getByText('フィールド1')).toBeInTheDocument();
    expect(screen.queryByText('フィールド2（非表示）')).not.toBeInTheDocument();
  });
});
