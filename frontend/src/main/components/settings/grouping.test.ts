import { describe, expect, it } from 'vitest';
import type { SettingsSection } from './types';
import { collectSettingsUpdateSections, groupSettingsSections } from './grouping';

function field(id: string, label = id, value: string | boolean = 'value') {
  return {
    id,
    label,
    description: '',
    type: typeof value === 'boolean' ? 'boolean' : 'text',
    recommended: false,
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
      ['obs', 'OBS 接続', 'group'],
      ['speech_transcriber', '文字起こし', 'group'],
    ]);
  });

  it('保存 payload は UI グループではなく元の source section id に戻す', () => {
    const grouped = groupSettingsSections([
      { id: 'webview', label: '表示', fields: [field('render_mode', '描画モード', 'gpu')] },
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
        fields: [field('enabled', '有効', true)],
        sourceSectionIds: ['general'],
        grouped: false,
      },
    ]);
  });
});
