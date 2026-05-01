/**
 * MetadataForm Component Tests
 *
 * 責務：
 * - MetadataForm コンポーネントの UI 動作を検証
 * - フィールド入力と値の反映を確認
 * - ドロップダウン選択を確認
 * - イベント発火を確認
 *
 * 分類: component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import MetadataForm from './MetadataForm.svelte';
import type { EditableMetadata } from '../../metadata/editable';

describe('MetadataForm.svelte', () => {
  // ========================================
  // 初期表示テスト
  // ========================================

  it('フォームが正しくレンダリングされる', () => {
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata } });

    // 主要なフィールドが表示されていることを確認
    expect(screen.getByLabelText('開始時間')).toBeInTheDocument();
    expect(screen.getByLabelText('マッチ')).toBeInTheDocument();
    expect(screen.getByLabelText('ルール')).toBeInTheDocument();
    expect(screen.getByLabelText('ステージ')).toBeInTheDocument();
    expect(screen.getByLabelText('レート')).toBeInTheDocument();
    expect(screen.getByLabelText('判定')).toBeInTheDocument();
    expect(screen.getByLabelText('キル数')).toBeInTheDocument();
    expect(screen.getByLabelText('デス数')).toBeInTheDocument();
    expect(screen.getByLabelText('スペシャル')).toBeInTheDocument();
    expect(screen.getByLabelText('金表彰')).toBeInTheDocument();
    expect(screen.getByLabelText('銀表彰')).toBeInTheDocument();
  });

  it('showGameMode=trueでゲームモードフィールドが表示される', () => {
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    const gameModeOptions = [
      { key: 'battle', label: 'バトル' },
      { key: 'salmon', label: 'サーモンラン' },
    ];

    render(MetadataForm, {
      props: { metadata, showGameMode: true, gameModeOptions },
    });

    expect(screen.getByLabelText('ゲームモード')).toBeInTheDocument();
  });

  it('showGameMode=falseでゲームモードフィールドが非表示になる', () => {
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata, showGameMode: false } });

    expect(screen.queryByLabelText('ゲームモード')).not.toBeInTheDocument();
  });

  // ========================================
  // テキスト・数値入力テスト（同型パターンを it.each で統合）
  // ========================================

  it.each([
    { label: '開始時間', input: '2026-03-14 12:00:00' },
    { label: 'レート', input: 'S+10' },
    { label: 'キル数', input: '10' },
    { label: 'デス数', input: '5' },
    { label: 'スペシャル', input: '3' },
    { label: '金表彰', input: '1' },
    { label: '銀表彰', input: '2' },
  ])('$label フィールドへの入力が反映される', async ({ label, input }) => {
    const user = userEvent.setup();
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata } });

    const field = screen.getByLabelText(label) as HTMLInputElement;
    await user.clear(field);
    await user.type(field, input);

    expect(field.value).toBe(input);
  });

  // ========================================
  // セレクト入力テスト（同型パターンを it.each で統合）
  // ========================================

  it.each([
    {
      label: 'マッチ',
      propName: 'matchOptions' as const,
      options: [
        { key: 'regular', label: 'レギュラーマッチ' },
        { key: 'anarchy', label: 'バンカラマッチ' },
      ],
      selectValue: 'regular',
    },
    {
      label: 'ルール',
      propName: 'ruleOptions' as const,
      options: [
        { key: 'turf_war', label: 'ナワバリ' },
        { key: 'rainmaker', label: 'ガチホコ' },
      ],
      selectValue: 'turf_war',
    },
    {
      label: 'ステージ',
      propName: 'stageOptions' as const,
      options: [
        { key: 'scorch_gorge', label: 'ユノハナ大渓谷' },
        { key: 'eeltail_alley', label: 'ゴンズイ地区' },
      ],
      selectValue: 'scorch_gorge',
    },
    {
      label: '判定',
      propName: 'judgementOptions' as const,
      options: [
        { key: 'WIN', label: '勝ち' },
        { key: 'LOSE', label: '負け' },
      ],
      selectValue: 'WIN',
    },
  ])('$label ドロップダウンで選択できる', async ({ label, propName, options, selectValue }) => {
    const user = userEvent.setup();
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata, [propName]: options } });

    const select = screen.getByLabelText(label) as HTMLSelectElement;
    await user.selectOptions(select, selectValue);

    expect(select.value).toBe(selectValue);
  });

  // ========================================
  // ブキ入力テスト
  // ========================================

  it('味方ブキフィールドが4つ表示される', () => {
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata } });

    expect(screen.getByLabelText('味方1')).toBeInTheDocument();
    expect(screen.getByLabelText('味方2')).toBeInTheDocument();
    expect(screen.getByLabelText('味方3')).toBeInTheDocument();
    expect(screen.getByLabelText('味方4')).toBeInTheDocument();
  });

  it('敵ブキフィールドが4つ表示される', () => {
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata } });

    expect(screen.getByLabelText('敵1')).toBeInTheDocument();
    expect(screen.getByLabelText('敵2')).toBeInTheDocument();
    expect(screen.getByLabelText('敵3')).toBeInTheDocument();
    expect(screen.getByLabelText('敵4')).toBeInTheDocument();
  });

  it('味方ブキフィールドへの入力が反映される', async () => {
    const user = userEvent.setup();
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata } });

    const ally1Input = screen.getByLabelText('味方1') as HTMLInputElement;
    await user.clear(ally1Input);
    await user.type(ally1Input, 'スプラシューター');

    expect(ally1Input.value).toBe('スプラシューター');
  });

  // ========================================
  // コールバックテスト
  // ========================================

  it('onFieldEditedが呼ばれる', async () => {
    const user = userEvent.setup();
    const onFieldEdited = vi.fn();
    const metadata: EditableMetadata = {
      gameMode: '',
      startedAt: '',
      match: '',
      rule: '',
      stage: '',
      rate: '',
      judgement: '',
      kill: 0,
      death: 0,
      special: 0,
      goldMedals: 0,
      silverMedals: 0,
      allies: ['', '', '', ''],
      enemies: ['', '', '', ''],
    };

    render(MetadataForm, { props: { metadata, onFieldEdited } });

    const rateInput = screen.getByLabelText('レート') as HTMLInputElement;
    await user.type(rateInput, 'S+');

    expect(onFieldEdited).toHaveBeenCalled();
  });
});
