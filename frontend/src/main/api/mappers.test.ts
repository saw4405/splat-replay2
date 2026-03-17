/**
 * API Mappers Unit Tests
 *
 * 責務：
 * - snake_case → camelCase 変換の正確性を検証
 * - null / 0 / 空文字列の区別処理を確認
 * - Boolean 正規化の動作を確認
 *
 * 分類: logic
 */

import { describe, it, expect } from 'vitest';
import {
  mapRecordedVideo,
  mapEditedVideo,
  mapEditUploadStatus,
  mapEditUploadTrigger,
  type RawRecordedVideo,
  type RawEditedVideo,
  type RawEditUploadStatus,
  type RawEditUploadTriggerResponse,
} from './mappers.ts';

describe('mapRecordedVideo', () => {
  // ========================================
  // Happy Path
  // ========================================

  it('完全なデータを正しくマッピングする', () => {
    const raw: RawRecordedVideo = {
      id: 'video_123',
      path: '/path/to/video.mp4',
      filename: 'video.mp4',
      started_at: '2026-03-14T12:00:00Z',
      game_mode: 'バトル',
      match: 'レギュラーマッチ',
      rule: 'ナワバリ',
      stage: 'ユノハナ大渓谷',
      rate: 'S+',
      judgement: 'WIN',
      kill: 10,
      death: 5,
      special: 3,
      gold_medals: 1,
      silver_medals: 2,
      allies: ['player1', 'player2', 'player3'],
      enemies: ['player4', 'player5', 'player6', 'player7'],
      hazard: 15,
      golden_egg: 30,
      power_egg: 500,
      rescue: 2,
      rescued: 1,
      has_subtitle: true,
      has_thumbnail: false,
      duration_seconds: 300,
      size_bytes: 1048576,
    };

    const result = mapRecordedVideo(raw);

    expect(result.id).toBe('video_123');
    expect(result.startedAt).toBe('2026-03-14T12:00:00Z');
    expect(result.gameMode).toBe('バトル');
    expect(result.match).toBe('レギュラーマッチ');
    expect(result.rule).toBe('ナワバリ');
    expect(result.stage).toBe('ユノハナ大渓谷');
    expect(result.rate).toBe('S+');
    expect(result.judgement).toBe('WIN');
    expect(result.kill).toBe(10);
    expect(result.death).toBe(5);
    expect(result.special).toBe(3);
    expect(result.goldMedals).toBe(1);
    expect(result.silverMedals).toBe(2);
    expect(result.allies).toEqual(['player1', 'player2', 'player3']);
    expect(result.enemies).toEqual(['player4', 'player5', 'player6', 'player7']);
    expect(result.hazard).toBe(15);
    expect(result.goldenEgg).toBe(30);
    expect(result.powerEgg).toBe(500);
    expect(result.rescue).toBe(2);
    expect(result.rescued).toBe(1);
    expect(result.hasSubtitles).toBe(true);
    expect(result.hasThumbnail).toBe(false);
    expect(result.durationSeconds).toBe(300);
    expect(result.sizeBytes).toBe(1048576);
  });

  // ========================================
  // Null Handling
  // ========================================

  it('null値をnullとして保持する', () => {
    const raw: RawRecordedVideo = {
      id: 'video_123',
      path: '/path/to/video.mp4',
      filename: 'video.mp4',
      started_at: null,
      game_mode: null,
      match: null,
      rule: null,
      stage: null,
      rate: null,
      judgement: null,
      kill: null,
      death: null,
      special: null,
      gold_medals: null,
      silver_medals: null,
      allies: null,
      enemies: null,
      hazard: null,
      golden_egg: null,
      power_egg: null,
      rescue: null,
      rescued: null,
      has_subtitle: false,
      has_thumbnail: false,
      duration_seconds: null,
      size_bytes: null,
    };

    const result = mapRecordedVideo(raw);

    expect(result.startedAt).toBeNull();
    expect(result.gameMode).toBeNull();
    expect(result.match).toBeNull();
    expect(result.rule).toBeNull();
    expect(result.stage).toBeNull();
    expect(result.rate).toBeNull();
    expect(result.judgement).toBeNull();
    expect(result.kill).toBeNull();
    expect(result.death).toBeNull();
    expect(result.special).toBeNull();
    expect(result.goldMedals).toBeNull();
    expect(result.silverMedals).toBeNull();
    expect(result.allies).toBeNull();
    expect(result.enemies).toBeNull();
    expect(result.hazard).toBeNull();
    expect(result.goldenEgg).toBeNull();
    expect(result.powerEgg).toBeNull();
    expect(result.rescue).toBeNull();
    expect(result.rescued).toBeNull();
    expect(result.durationSeconds).toBeNull();
    expect(result.sizeBytes).toBeNull();
  });

  it('0をnullではなく0として保持する', () => {
    const raw: RawRecordedVideo = {
      id: 'video_123',
      path: '/path/to/video.mp4',
      filename: 'video.mp4',
      started_at: null,
      game_mode: null,
      match: null,
      rule: null,
      stage: null,
      rate: null,
      judgement: null,
      kill: 0,
      death: 0,
      special: 0,
      gold_medals: 0,
      silver_medals: 0,
      allies: null,
      enemies: null,
      hazard: 0,
      golden_egg: 0,
      power_egg: 0,
      rescue: 0,
      rescued: 0,
      has_subtitle: false,
      has_thumbnail: false,
      duration_seconds: 0,
      size_bytes: 0,
    };

    const result = mapRecordedVideo(raw);

    expect(result.kill).toBe(0);
    expect(result.death).toBe(0);
    expect(result.special).toBe(0);
    expect(result.goldMedals).toBe(0);
    expect(result.silverMedals).toBe(0);
    expect(result.hazard).toBe(0);
    expect(result.goldenEgg).toBe(0);
    expect(result.powerEgg).toBe(0);
    expect(result.rescue).toBe(0);
    expect(result.rescued).toBe(0);
    expect(result.durationSeconds).toBe(0);
    expect(result.sizeBytes).toBe(0);
  });

  it('空配列を処理できる', () => {
    const raw: RawRecordedVideo = {
      id: 'video_123',
      path: '/path/to/video.mp4',
      filename: 'video.mp4',
      started_at: null,
      game_mode: null,
      match: null,
      rule: null,
      stage: null,
      rate: null,
      judgement: null,
      kill: null,
      death: null,
      special: null,
      gold_medals: null,
      silver_medals: null,
      allies: [],
      enemies: [],
      hazard: null,
      golden_egg: null,
      power_egg: null,
      rescue: null,
      rescued: null,
      has_subtitle: false,
      has_thumbnail: false,
      duration_seconds: null,
      size_bytes: null,
    };

    const result = mapRecordedVideo(raw);

    expect(result.allies).toEqual([]);
    expect(result.enemies).toEqual([]);
  });

  // ========================================
  // Boolean Normalization
  // ========================================

  it('has_subtitleとhas_thumbnailをBooleanに正規化する', () => {
    const raw: RawRecordedVideo = {
      id: 'video_123',
      path: '/path/to/video.mp4',
      filename: 'video.mp4',
      started_at: null,
      game_mode: null,
      match: null,
      rule: null,
      stage: null,
      rate: null,
      judgement: null,
      kill: null,
      death: null,
      special: null,
      gold_medals: null,
      silver_medals: null,
      allies: null,
      enemies: null,
      hazard: null,
      golden_egg: null,
      power_egg: null,
      rescue: null,
      rescued: null,
      has_subtitle: true,
      has_thumbnail: false,
      duration_seconds: null,
      size_bytes: null,
    };

    const result = mapRecordedVideo(raw);

    expect(result.hasSubtitles).toBe(true);
    expect(result.hasThumbnail).toBe(false);
  });
});

describe('mapEditedVideo', () => {
  // ========================================
  // Happy Path
  // ========================================

  it('完全なデータを正しくマッピングする', () => {
    const raw: RawEditedVideo = {
      id: 'edited_123',
      path: '/path/to/edited.mkv',
      filename: 'edited.mkv',
      has_subtitle: true,
      has_thumbnail: true,
      duration_seconds: 600,
      updated_at: '2026-03-14T13:00:00Z',
      size_bytes: 2097152,
      metadata: {
        title: 'テストタイトル',
        description: 'テスト説明',
        custom_field: 'カスタム値',
      },
      title: 'タイトル',
      description: '説明文',
    };

    const result = mapEditedVideo(raw);

    expect(result.id).toBe('edited_123');
    expect(result.path).toBe('/path/to/edited.mkv');
    expect(result.filename).toBe('edited.mkv');
    expect(result.hasSubtitles).toBe(true);
    expect(result.hasThumbnail).toBe(true);
    expect(result.durationSeconds).toBe(600);
    expect(result.updatedAt).toBe('2026-03-14T13:00:00Z');
    expect(result.sizeBytes).toBe(2097152);
    expect(result.metadata).toEqual({
      title: 'テストタイトル',
      description: 'テスト説明',
      custom_field: 'カスタム値',
    });
    expect(result.title).toBe('タイトル');
    expect(result.description).toBe('説明文');
  });

  // ========================================
  // Metadata Handling
  // ========================================

  it('metadataがnullの場合は空オブジェクトを返す', () => {
    const raw: RawEditedVideo = {
      id: 'edited_123',
      path: '/path/to/edited.mkv',
      filename: 'edited.mkv',
      has_subtitle: false,
      has_thumbnail: false,
      duration_seconds: null,
      updated_at: null,
      size_bytes: null,
      metadata: null,
      title: null,
      description: null,
    };

    const result = mapEditedVideo(raw);

    expect(result.metadata).toEqual({});
  });

  it('metadata内のnull値をnullとして保持する', () => {
    const raw: RawEditedVideo = {
      id: 'edited_123',
      path: '/path/to/edited.mkv',
      filename: 'edited.mkv',
      has_subtitle: false,
      has_thumbnail: false,
      duration_seconds: null,
      updated_at: null,
      size_bytes: null,
      metadata: {
        title: 'タイトル',
        description: null,
        custom_field: null,
      },
      title: null,
      description: null,
    };

    const result = mapEditedVideo(raw);

    expect(result.metadata).toEqual({
      title: 'タイトル',
      description: null,
      custom_field: null,
    });
  });
});

describe('mapEditUploadStatus', () => {
  // ========================================
  // Happy Path
  // ========================================

  it('完全なデータを正しくマッピングする', () => {
    const raw: RawEditUploadStatus = {
      state: 'running',
      started_at: '2026-03-14T14:00:00Z',
      finished_at: null,
      error: null,
      sleep_after_upload_default: true,
      sleep_after_upload_effective: false,
      sleep_after_upload_overridden: true,
    };

    const result = mapEditUploadStatus(raw);

    expect(result.state).toBe('running');
    expect(result.startedAt).toBe('2026-03-14T14:00:00Z');
    expect(result.finishedAt).toBeNull();
    expect(result.error).toBeNull();
    expect(result.sleepAfterUploadDefault).toBe(true);
    expect(result.sleepAfterUploadEffective).toBe(false);
    expect(result.sleepAfterUploadOverridden).toBe(true);
  });

  // ========================================
  // State Variations
  // ========================================

  it.each([['idle' as const], ['running' as const], ['succeeded' as const], ['failed' as const]])(
    'state=%sを正しく処理する',
    (state) => {
      const raw: RawEditUploadStatus = {
        state,
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      };

      const result = mapEditUploadStatus(raw);

      expect(result.state).toBe(state);
    }
  );

  // ========================================
  // Boolean Normalization
  // ========================================

  it('sleep_after_upload_*フィールドをBooleanに正規化する', () => {
    const raw: RawEditUploadStatus = {
      state: 'idle',
      started_at: null,
      finished_at: null,
      error: null,
      sleep_after_upload_default: true,
      sleep_after_upload_effective: true,
      sleep_after_upload_overridden: false,
    };

    const result = mapEditUploadStatus(raw);

    expect(typeof result.sleepAfterUploadDefault).toBe('boolean');
    expect(typeof result.sleepAfterUploadEffective).toBe('boolean');
    expect(typeof result.sleepAfterUploadOverridden).toBe('boolean');
    expect(result.sleepAfterUploadDefault).toBe(true);
    expect(result.sleepAfterUploadEffective).toBe(true);
    expect(result.sleepAfterUploadOverridden).toBe(false);
  });

  // ========================================
  // Error Handling
  // ========================================

  it('failedステートでerrorメッセージを保持する', () => {
    const raw: RawEditUploadStatus = {
      state: 'failed',
      started_at: '2026-03-14T14:00:00Z',
      finished_at: '2026-03-14T14:05:00Z',
      error: 'アップロードに失敗しました',
      sleep_after_upload_default: false,
      sleep_after_upload_effective: false,
      sleep_after_upload_overridden: false,
    };

    const result = mapEditUploadStatus(raw);

    expect(result.state).toBe('failed');
    expect(result.error).toBe('アップロードに失敗しました');
    expect(result.finishedAt).toBe('2026-03-14T14:05:00Z');
  });
});

describe('mapEditUploadTrigger', () => {
  // ========================================
  // Happy Path
  // ========================================

  it('accepted=trueの完全なレスポンスをマッピングする', () => {
    const raw: RawEditUploadTriggerResponse = {
      accepted: true,
      status: {
        state: 'running',
        started_at: '2026-03-14T14:00:00Z',
        finished_at: null,
        error: null,
        sleep_after_upload_default: true,
        sleep_after_upload_effective: true,
        sleep_after_upload_overridden: false,
      },
      message: '編集・アップロード処理を開始しました',
    };

    const result = mapEditUploadTrigger(raw);

    expect(result.accepted).toBe(true);
    expect(result.status.state).toBe('running');
    expect(result.status.startedAt).toBe('2026-03-14T14:00:00Z');
    expect(result.message).toBe('編集・アップロード処理を開始しました');
  });

  it('accepted=falseのレスポンスをマッピングする', () => {
    const raw: RawEditUploadTriggerResponse = {
      accepted: false,
      status: {
        state: 'idle',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
      message: '既に処理が実行中です',
    };

    const result = mapEditUploadTrigger(raw);

    expect(result.accepted).toBe(false);
    expect(result.status.state).toBe('idle');
    expect(result.message).toBe('既に処理が実行中です');
  });

  it('messageがnullの場合もnullとして保持する', () => {
    const raw: RawEditUploadTriggerResponse = {
      accepted: true,
      status: {
        state: 'running',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      },
      message: null,
    };

    const result = mapEditUploadTrigger(raw);

    expect(result.message).toBeNull();
  });
});
