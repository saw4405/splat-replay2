import assert from 'node:assert/strict';
import test from 'node:test';

import {
  applyIncomingLiveMetadata,
  buildLiveMetadataPayload,
  createEmptyLiveManualEditState,
  createEmptyLiveMetadataState,
} from './live.ts';

test('buildLiveMetadataPayload は手動編集した空文字フィールドを null クリアとして保持する', () => {
  const metadata = createEmptyLiveMetadataState();
  const manuallyEdited = createEmptyLiveManualEditState();

  metadata.match = '';
  metadata.rate = '';
  metadata.started_at = '';
  manuallyEdited.match = true;
  manuallyEdited.rate = true;
  manuallyEdited.started_at = true;

  assert.deepStrictEqual(buildLiveMetadataPayload(metadata, manuallyEdited), {
    match: null,
    rate: null,
    started_at: null,
  });
});

test('buildLiveMetadataPayload は 0 とブキ配列を更新対象として含める', () => {
  const metadata = createEmptyLiveMetadataState();
  const manuallyEdited = createEmptyLiveManualEditState();

  metadata.kill = 0;
  metadata.gold_medals = 0;
  metadata.allies = ['A', 'B', '', ''] as [string, string, string, string];
  manuallyEdited.kill = true;
  manuallyEdited.gold_medals = true;
  manuallyEdited.allies = true;

  assert.deepStrictEqual(buildLiveMetadataPayload(metadata, manuallyEdited), {
    kill: 0,
    gold_medals: 0,
    allies: ['A', 'B', '', ''],
  });
});

test('applyIncomingLiveMetadata は手動編集済みの値を保持しつつ未編集値を更新する', () => {
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
  assert.deepStrictEqual(result.metadata.allies, ['S1', 'S2', 'S3', 'S4']);
  assert.match(result.skippedFields.join(','), /match \(手動編集済み\)/);
  assert.match(result.skippedFields.join(','), /gold_medals \(手動編集済み\)/);
});
