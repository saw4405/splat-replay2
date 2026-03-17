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
  // テキスト入力テスト
  // ========================================

  it('開始時間フィールドへの入力が反映される', async () => {
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

    const startedAtInput = screen.getByLabelText('開始時間') as HTMLInputElement;
    await user.clear(startedAtInput);
    await user.type(startedAtInput, '2026-03-14 12:00:00');

    expect(startedAtInput.value).toBe('2026-03-14 12:00:00');
  });

  it('レートフィールドへの入力が反映される', async () => {
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

    const rateInput = screen.getByLabelText('レート') as HTMLInputElement;
    await user.clear(rateInput);
    await user.type(rateInput, 'S+10');

    expect(rateInput.value).toBe('S+10');
  });

  // ========================================
  // 数値入力テスト
  // ========================================

  it('キル数フィールドへの入力が反映される', async () => {
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

    const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
    await user.clear(killInput);
    await user.type(killInput, '10');

    expect(killInput.value).toBe('10');
  });

  it('デス数フィールドへの入力が反映される', async () => {
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

    const deathInput = screen.getByLabelText('デス数') as HTMLInputElement;
    await user.clear(deathInput);
    await user.type(deathInput, '5');

    expect(deathInput.value).toBe('5');
  });

  it('スペシャル数フィールドへの入力が反映される', async () => {
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

    const specialInput = screen.getByLabelText('スペシャル') as HTMLInputElement;
    await user.clear(specialInput);
    await user.type(specialInput, '3');

    expect(specialInput.value).toBe('3');
  });

  // ========================================
  // セレクト入力テスト
  // ========================================

  it('マッチドロップダウンで選択できる', async () => {
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

    const matchOptions = [
      { key: 'regular', label: 'レギュラーマッチ' },
      { key: 'anarchy', label: 'バンカラマッチ' },
    ];

    render(MetadataForm, { props: { metadata, matchOptions } });

    const matchSelect = screen.getByLabelText('マッチ') as HTMLSelectElement;
    await user.selectOptions(matchSelect, 'regular');

    expect(matchSelect.value).toBe('regular');
  });

  it('ルールドロップダウンで選択できる', async () => {
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

    const ruleOptions = [
      { key: 'turf_war', label: 'ナワバリ' },
      { key: 'rainmaker', label: 'ガチホコ' },
    ];

    render(MetadataForm, { props: { metadata, ruleOptions } });

    const ruleSelect = screen.getByLabelText('ルール') as HTMLSelectElement;
    await user.selectOptions(ruleSelect, 'turf_war');

    expect(ruleSelect.value).toBe('turf_war');
  });

  it('ステージドロップダウンで選択できる', async () => {
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

    const stageOptions = [
      { key: 'scorch_gorge', label: 'ユノハナ大渓谷' },
      { key: 'eeltail_alley', label: 'ゴンズイ地区' },
    ];

    render(MetadataForm, { props: { metadata, stageOptions } });

    const stageSelect = screen.getByLabelText('ステージ') as HTMLSelectElement;
    await user.selectOptions(stageSelect, 'scorch_gorge');

    expect(stageSelect.value).toBe('scorch_gorge');
  });

  it('判定ドロップダウンで選択できる', async () => {
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

    const judgementOptions = [
      { key: 'WIN', label: '勝ち' },
      { key: 'LOSE', label: '負け' },
    ];

    render(MetadataForm, { props: { metadata, judgementOptions } });

    const judgementSelect = screen.getByLabelText('判定') as HTMLSelectElement;
    await user.selectOptions(judgementSelect, 'WIN');

    expect(judgementSelect.value).toBe('WIN');
  });

  // ========================================
  // メダル入力テスト
  // ========================================

  it('金表彰フィールドへの入力が反映される', async () => {
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

    const goldMedalsInput = screen.getByLabelText('金表彰') as HTMLInputElement;
    await user.clear(goldMedalsInput);
    await user.type(goldMedalsInput, '1');

    expect(goldMedalsInput.value).toBe('1');
  });

  it('銀表彰フィールドへの入力が反映される', async () => {
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

    const silverMedalsInput = screen.getByLabelText('銀表彰') as HTMLInputElement;
    await user.clear(silverMedalsInput);
    await user.type(silverMedalsInput, '2');

    expect(silverMedalsInput.value).toBe('2');
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
