import assert from 'node:assert/strict';
import test from 'node:test';

import { toEditableMetadata, toMetadataUpdatePayload } from './editable.ts';

test('toEditableMetadata は開始時間を編集フォーム向け書式へ正規化する', () => {
  const editable = toEditableMetadata({
    id: 'video-1',
    path: 'recorded/video-1.mp4',
    filename: 'video-1.mp4',
    startedAt: '2026-03-09T12:34:56',
    gameMode: 'BATTLE',
    match: 'X',
    rule: 'AREA',
    stage: 'MASSUN',
    rate: '2500',
    judgement: 'WIN',
    kill: 10,
    death: 3,
    special: 2,
    goldMedals: 2,
    silverMedals: 1,
    allies: ['A', 'B', 'C', 'D'],
    enemies: ['E', 'F', 'G', 'H'],
    hazard: null,
    goldenEgg: null,
    powerEgg: null,
    rescue: null,
    rescued: null,
    hasSubtitles: true,
    hasThumbnail: true,
    durationSeconds: 120,
    sizeBytes: 1024,
  });

  assert.equal(editable.startedAt, '2026-03-09 12:34:56');
});

test('toMetadataUpdatePayload は開始時間を started_at へ変換し書式も正規化する', () => {
  const payload = toMetadataUpdatePayload({
    startedAt: '2026-03-09T12:34:56.789',
    match: 'X',
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
  });

  assert.deepEqual(payload, {
    started_at: '2026-03-09 12:34:56',
    match: 'X',
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
  });
});
