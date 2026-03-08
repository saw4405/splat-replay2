import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyIncomingLiveMetadata,
  buildLiveMetadataPayload,
  createEmptyLiveManualEditState,
  createEmptyLiveMetadataState,
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

test('buildLiveMetadataPayload returns empty object when nothing was edited', () => {
  assert.deepEqual(buildLiveMetadataPayload(createMetadata(), createEditedFlags()), {});
});

test('buildLiveMetadataPayload keeps explicit clears as null', () => {
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

  assert.deepEqual(buildLiveMetadataPayload(metadata, edited), {
    started_at: null,
    match: null,
    rule: null,
    rate: null,
    judgement: null,
    stage: null,
  });
});

test('buildLiveMetadataPayload preserves zero values and weapon slots', () => {
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

  assert.deepEqual(buildLiveMetadataPayload(metadata, edited), {
    kill: 0,
    death: 0,
    special: 0,
    gold_medals: 0,
    silver_medals: 0,
    allies: ['', '', '', ''],
    enemies: ['S1', 'S2', 'S3', 'S4'],
  });
});

test('applyIncomingLiveMetadata keeps manual values and updates untouched fields', () => {
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

  assert.equal(result.metadata.game_mode, 'BATTLE');
  assert.equal(result.metadata.match, 'MANUAL_MATCH');
  assert.equal(result.metadata.rule, 'AREA');
  assert.equal(result.metadata.gold_medals, 3);
  assert.equal(result.metadata.silver_medals, 0);
  assert.deepEqual(result.metadata.allies, ['S1', 'S2', 'S3', 'S4']);
  assert.match(result.skippedFields.join(','), /match \(手動編集済み\)/);
  assert.match(result.skippedFields.join(','), /gold_medals \(手動編集済み\)/);
});
