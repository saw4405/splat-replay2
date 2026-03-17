import { describe, it, expect } from 'vitest';

import {
  applyIncomingLiveMetadata,
  buildLiveMetadataPayload,
  createEmptyLiveManualEditState,
  createEmptyLiveMetadataState,
  toEditableLiveMetadata,
  toLiveMetadataState,
  type LiveManualEditState,
  type LiveMetadataState,
} from './live.ts';

function createMetadata(): LiveMetadataState {
  return {
    game_mode: 'BATTLE',
    started_at: '2026-03-08 12:00:00',
    match: 'X',
    rule: 'AREA',
    rate: '2500',
    judgement: 'WIN',
    stage: 'YAGARA_MARKET',
    kill: 8,
    death: 4,
    special: 2,
    gold_medals: 2,
    silver_medals: 1,
    allies: ['A', 'B', 'C', 'D'],
    enemies: ['E', 'F', 'G', 'H'],
  };
}

function createEditedFlags(): LiveManualEditState {
  return {
    game_mode: false,
    started_at: false,
    match: false,
    rule: false,
    rate: false,
    judgement: false,
    stage: false,
    kill: false,
    death: false,
    special: false,
    gold_medals: false,
    silver_medals: false,
    allies: false,
    enemies: false,
  };
}

describe('live metadata', () => {
  it('buildLiveMetadataPayload returns empty object when nothing was edited', () => {
    expect(buildLiveMetadataPayload(createMetadata(), createEditedFlags())).toEqual({});
  });

  it('buildLiveMetadataPayload keeps explicit clears as null', () => {
    const metadata = createMetadata();
    metadata.started_at = '';
    metadata.match = '';
    metadata.rule = '';
    metadata.rate = '';
    metadata.judgement = '';
    metadata.stage = '';

    const edited = createEditedFlags();
    edited.started_at = true;
    edited.match = true;
    edited.rule = true;
    edited.rate = true;
    edited.judgement = true;
    edited.stage = true;

    expect(buildLiveMetadataPayload(metadata, edited)).toEqual({
      started_at: null,
      match: null,
      rule: null,
      rate: null,
      judgement: null,
      stage: null,
    });
  });

  it('buildLiveMetadataPayload preserves zero values and weapon slots', () => {
    const metadata = createMetadata();
    metadata.kill = 0;
    metadata.death = 0;
    metadata.special = 0;
    metadata.gold_medals = 0;
    metadata.silver_medals = 0;
    metadata.allies = ['', '', '', ''];
    metadata.enemies = ['S1', 'S2', 'S3', 'S4'];

    const edited = createEditedFlags();
    edited.kill = true;
    edited.death = true;
    edited.special = true;
    edited.gold_medals = true;
    edited.silver_medals = true;
    edited.allies = true;
    edited.enemies = true;

    expect(buildLiveMetadataPayload(metadata, edited)).toEqual({
      kill: 0,
      death: 0,
      special: 0,
      gold_medals: 0,
      silver_medals: 0,
      allies: ['', '', '', ''],
      enemies: ['S1', 'S2', 'S3', 'S4'],
    });
  });

  it('applyIncomingLiveMetadata keeps manual values and updates untouched fields', () => {
    const metadata = createEmptyLiveMetadataState();
    const manuallyEdited = createEmptyLiveManualEditState();

    metadata.match = 'MANUAL_MATCH';
    metadata.gold_medals = 3;
    manuallyEdited.match = true;
    manuallyEdited.gold_medals = true;

    const result = applyIncomingLiveMetadata(metadata, manuallyEdited, {
      game_mode: 'BATTLE',
      match: 'AUTO_MATCH',
      rule: 'AREA',
      gold_medals: 1,
      silver_medals: 3,
      allies: ['S1', 'S2', 'S3', 'S4'],
    });

    expect(result.metadata.game_mode).toBe('BATTLE');
    expect(result.metadata.match).toBe('MANUAL_MATCH');
    expect(result.metadata.rule).toBe('AREA');
    expect(result.metadata.gold_medals).toBe(3);
    expect(result.metadata.silver_medals).toBe(0);
    expect(result.metadata.allies).toEqual(['S1', 'S2', 'S3', 'S4']);
    expect(result.skippedFields.join(',')).toContain('match (手動編集済み)');
    expect(result.skippedFields.join(',')).toContain('gold_medals (手動編集済み)');
  });

  it('toEditableLiveMetadata は live state を共通フォーム状態へ変換する', () => {
    const editable = toEditableLiveMetadata(createMetadata());

    expect(editable.gameMode).toBe('BATTLE');
    expect(editable.startedAt).toBe('2026-03-08 12:00:00');
    expect(editable.goldMedals).toBe(2);
    expect(editable.allies).toEqual(['A', 'B', 'C', 'D']);
  });

  it('toLiveMetadataState は共通フォーム状態を live state へ戻し表彰数を正規化する', () => {
    const editable = toEditableLiveMetadata(createMetadata());
    editable.goldMedals = 2;
    editable.silverMedals = 3;

    const live = toLiveMetadataState(editable);

    expect(live.game_mode).toBe('BATTLE');
    expect(live.started_at).toBe('2026-03-08 12:00:00');
    expect(live.gold_medals).toBe(2);
    expect(live.silver_medals).toBe(1);
  });
});
