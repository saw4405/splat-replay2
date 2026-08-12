import { describe, expect, it } from 'vitest';
import type { SettingsSection } from './types';
import {
  collectSettingsUpdateSections,
  filterSettingsFieldsByDisplayMode,
  filterSettingsSectionsByDisplayMode,
  groupSettingsSections,
} from './grouping';

function field(id: string, label = id, value: string | boolean = 'value') {
  return {
    id,
    label,
    description: '',
    type: typeof value === 'boolean' ? 'boolean' : 'text',
    requirement: 'optional' as const,
    display_level: 'advanced' as const,
    user_editable: true,
    value,
  };
}

describe('settings grouping', () => {
  it('既存 section を固定順の5グループへ変換する', () => {
    const grouped = groupSettingsSections([
      { id: 'upload', label: 'アップロード', fields: [field('privacy_status')] },
      { id: 'speech_transcriber', label: '文字起こし', fields: [field('enabled', '有効', true)] },
      { id: 'video_edit', label: '動画編集', fields: [field('title_template')] },
      { id: 'obs', label: 'OBS 接続', fields: [field('websocket_host')] },
      { id: 'webview', label: '表示', fields: [field('render_mode')] },
      { id: 'capture_device', label: 'Capture device settings.', fields: [field('name')] },
      { id: 'behavior', label: '動作', fields: [field('edit_after_power_off', '編集開始', true)] },
      { id: 'record', label: '録画', fields: [field('width', '幅')] },
    ]);

    expect(grouped.map((section) => [section.id, section.label])).toEqual([
      ['behavior', '動作'],
      ['display', '表示'],
      ['recording', '録画'],
      ['edit', '編集'],
      ['upload', 'アップロード'],
    ]);
  });

  it('録画グループは録画関連 source section を内部 group として持つ', () => {
    const grouped = groupSettingsSections([
      { id: 'capture_device', label: 'Capture device settings.', fields: [field('name')] },
      { id: 'obs', label: 'OBS 接続', fields: [field('websocket_host')] },
      {
        id: 'record',
        label: '録画',
        fields: [{ ...field('width'), user_editable: false }],
      },
      { id: 'speech_transcriber', label: '文字起こし', fields: [field('enabled', '有効', true)] },
    ]);

    const recording = grouped.find((section) => section.id === 'recording');

    expect(recording?.fields.map((item) => [item.id, item.label, item.type])).toEqual([
      ['capture_device', 'キャプチャデバイス', 'group'],
      ['obs', 'OBS接続', 'group'],
      ['speech_transcriber', '文字起こし', 'group'],
    ]);
  });

  it('基本設定では basic の子を持つ録画区分だけを表示する', () => {
    const grouped = groupSettingsSections([
      {
        id: 'capture_device',
        label: 'Capture device settings.',
        fields: [
          {
            ...field('name', 'キャプチャデバイス名'),
            requirement: 'required',
            display_level: 'basic',
          },
        ],
      },
      { id: 'obs', label: 'OBS 接続', fields: [field('websocket_host', 'ホスト')] },
      { id: 'speech_transcriber', label: '文字起こし', fields: [field('enabled', '有効', true)] },
    ]);
    const recording = grouped.find((section) => section.id === 'recording');

    expect(recording).toBeDefined();
    const basicFields = filterSettingsFieldsByDisplayMode(recording?.fields ?? [], 'basic');

    expect(basicFields.map((item) => item.id)).toEqual(['capture_device']);
    expect(basicFields[0]?.children?.map((child) => child.id)).toEqual(['name']);
    expect(recording?.fields.map((item) => item.id)).toEqual([
      'capture_device',
      'obs',
      'speech_transcriber',
    ]);
  });

  it('基本設定では basic フィールドがあるセクションだけを固定順で返す', () => {
    const grouped = groupSettingsSections([
      {
        id: 'behavior',
        label: '動作',
        fields: [{ ...field('behavior_basic'), display_level: 'basic' }],
      },
      { id: 'webview', label: '表示', fields: [field('render_mode')] },
      {
        id: 'capture_device',
        label: 'Capture device settings.',
        fields: [{ ...field('device_name'), display_level: 'basic' }],
      },
      { id: 'video_edit', label: '動画編集', fields: [field('title_template')] },
      {
        id: 'upload',
        label: 'アップロード',
        fields: [{ ...field('privacy_status'), display_level: 'basic' }],
      },
    ]);

    const basicSections = filterSettingsSectionsByDisplayMode(grouped, 'basic');

    expect(basicSections.map((section) => section.id)).toEqual(['behavior', 'recording', 'upload']);
    expect(
      basicSections.find((section) => section.id === 'recording')?.fields[0]?.children
    ).toEqual([expect.objectContaining({ id: 'device_name' })]);
    expect(filterSettingsSectionsByDisplayMode(grouped, 'all')).toBe(grouped);
  });

  it('すべての設定では全フィールドの参照をそのまま返す', () => {
    const grouped = groupSettingsSections([
      { id: 'behavior', label: '動作', fields: [field('edit_after_power_off')] },
    ]);
    const behavior = grouped.find((section) => section.id === 'behavior');

    expect(behavior).toBeDefined();
    expect(filterSettingsFieldsByDisplayMode(behavior?.fields ?? [], 'all')).toBe(behavior?.fields);
  });

  it('表示タブは webview と remote_access を通常フィールドとして平坦化する', () => {
    const grouped = groupSettingsSections([
      { id: 'webview', label: '表示', fields: [field('render_mode', '描画モード', 'gpu')] },
      {
        id: 'remote_access',
        label: 'LAN 公開',
        fields: [field('enabled', 'LAN 公開', false)],
      },
    ]);

    const display = grouped.find((section) => section.id === 'display');

    expect(display?.fields.map((item) => [item.id, item.type, item.sourceSectionId])).toEqual([
      ['render_mode', 'text', 'webview'],
      ['enabled', 'boolean', 'remote_access'],
    ]);
    expect(display?.fields.every((item) => item.type !== 'group')).toBe(true);
  });

  it('表示タブ内で field id が重複しても保存元を区別する', () => {
    const grouped = groupSettingsSections([
      { id: 'webview', label: '表示', fields: [field('enabled', '描画を有効化', true)] },
      {
        id: 'remote_access',
        label: 'LAN 公開',
        fields: [field('enabled', 'LAN 公開', false)],
      },
    ]);

    expect(collectSettingsUpdateSections(grouped)).toEqual([
      { id: 'webview', values: { enabled: true } },
      { id: 'remote_access', values: { enabled: false } },
    ]);
  });

  it('保存 payload は UI グループではなく元の source section id に戻す', () => {
    const grouped = groupSettingsSections([
      { id: 'webview', label: '表示', fields: [field('render_mode', '描画モード', 'gpu')] },
      {
        id: 'remote_access',
        label: 'LAN 公開',
        fields: [field('enabled', 'LAN 公開', false)],
      },
      {
        id: 'capture_device',
        label: 'Capture device settings.',
        fields: [field('name', '名前', 'Capture')],
      },
      { id: 'obs', label: 'OBS 接続', fields: [field('websocket_host', 'ホスト', 'localhost')] },
      { id: 'speech_transcriber', label: '文字起こし', fields: [field('enabled', '有効', false)] },
    ]);

    expect(collectSettingsUpdateSections(grouped)).toEqual([
      { id: 'webview', values: { render_mode: 'gpu' } },
      { id: 'remote_access', values: { enabled: false } },
      { id: 'capture_device', values: { name: 'Capture' } },
      { id: 'obs', values: { websocket_host: 'localhost' } },
      { id: 'speech_transcriber', values: { enabled: false } },
    ]);
  });

  it('既知 section がないテスト用レスポンスは従来どおり編集可能 section として扱う', () => {
    const unknownSections: SettingsSection[] = [
      {
        id: 'general',
        label: '一般設定',
        fields: [field('enabled', '有効', true), { ...field('hidden'), user_editable: false }],
      },
    ];

    expect(groupSettingsSections(unknownSections)).toEqual([
      {
        id: 'general',
        label: '一般設定',
        fields: [{ ...field('enabled', '有効', true), sourceSectionId: 'general' }],
        sourceSectionIds: ['general'],
      },
    ]);
  });
});
