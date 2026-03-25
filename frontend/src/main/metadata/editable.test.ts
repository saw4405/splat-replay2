import { describe, it, expect } from 'vitest';

import {
  normaliseEditableMetadataSelectFields,
  toEditableMetadata,
  toMetadataUpdatePayload,
} from './editable.ts';

describe('editable metadata', () => {
  it('toEditableMetadata は開始時間を編集フォーム向け書式へ正規化する', () => {
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

    expect(editable.startedAt).toBe('2026-03-09 12:34:56');
  });

  it('toMetadataUpdatePayload は開始時間を started_at へ変換し書式も正規化する', () => {
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

    expect(payload).toEqual({
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

  it('normaliseEditableMetadataSelectFields は表示ラベルを select 用キーへ変換する', () => {
    const editable = normaliseEditableMetadataSelectFields(
      {
        gameMode: 'バトル',
        startedAt: '2026-03-09 12:34:56',
        match: 'レギュラーマッチ',
        rule: 'ナワバリ',
        stage: 'ナンプラー遺跡',
        rate: '',
        judgement: 'WIN',
        kill: 10,
        death: 3,
        special: 2,
        goldMedals: 2,
        silverMedals: 1,
        allies: ['A', 'B', 'C', 'D'],
        enemies: ['E', 'F', 'G', 'H'],
      },
      {
        gameModes: [{ key: 'BATTLE', label: 'バトル' }],
        matches: [{ key: 'REGULAR', label: 'レギュラーマッチ' }],
        rules: [{ key: 'TURF_WAR', label: 'ナワバリ' }],
        stages: [{ key: 'BLUEFIN_DEPOT', label: 'ナンプラー遺跡' }],
        judgements: [{ key: 'WIN', label: '勝ち' }],
      }
    );

    expect(editable.gameMode).toBe('BATTLE');
    expect(editable.match).toBe('REGULAR');
    expect(editable.rule).toBe('TURF_WAR');
    expect(editable.stage).toBe('BLUEFIN_DEPOT');
    expect(editable.judgement).toBe('WIN');
  });

  it('normaliseEditableMetadataSelectFields は既にキー値ならそのまま維持する', () => {
    const editable = normaliseEditableMetadataSelectFields(
      {
        gameMode: 'BATTLE',
        startedAt: '2026-03-09 12:34:56',
        match: 'REGULAR',
        rule: 'TURF_WAR',
        stage: 'BLUEFIN_DEPOT',
        rate: '',
        judgement: 'WIN',
        kill: 10,
        death: 3,
        special: 2,
        goldMedals: 2,
        silverMedals: 1,
        allies: ['A', 'B', 'C', 'D'],
        enemies: ['E', 'F', 'G', 'H'],
      },
      {
        gameModes: [{ key: 'BATTLE', label: 'バトル' }],
        matches: [{ key: 'REGULAR', label: 'レギュラーマッチ' }],
        rules: [{ key: 'TURF_WAR', label: 'ナワバリ' }],
        stages: [{ key: 'BLUEFIN_DEPOT', label: 'ナンプラー遺跡' }],
        judgements: [{ key: 'WIN', label: '勝ち' }],
      }
    );

    expect(editable.gameMode).toBe('BATTLE');
    expect(editable.match).toBe('REGULAR');
    expect(editable.rule).toBe('TURF_WAR');
    expect(editable.stage).toBe('BLUEFIN_DEPOT');
    expect(editable.judgement).toBe('WIN');
  });
});
