/**
 * APIデータマッパー
 *
 * 責務：
 * - バックエンドの命名規則(snake_case)をフロントエンド(camelCase)に変換
 * - 値の正規化
 */

import type {
  RecordedVideo,
  EditedVideo,
  EditUploadStatus,
  EditUploadTriggerResponse,
} from './types';

// バックエンドのレスポンス型
export type RawRecordedVideo = {
  id: string;
  path: string;
  filename: string;
  started_at: string | null;
  game_mode: string | null;
  match: string | null;
  rule: string | null;
  stage: string | null;
  rate: string | null;
  judgement: string | null;
  kill: number | null;
  death: number | null;
  special: number | null;
  allies: string[] | null;
  enemies: string[] | null;
  hazard: number | null;
  golden_egg: number | null;
  power_egg: number | null;
  rescue: number | null;
  rescued: number | null;
  has_subtitle: boolean;
  has_thumbnail: boolean;
  duration_seconds: number | null;
  size_bytes: number | null;
};

export type RawEditedVideo = {
  id: string;
  path: string;
  filename: string;
  has_subtitle: boolean;
  has_thumbnail: boolean;
  duration_seconds: number | null;
  updated_at: string | null;
  size_bytes: number | null;
  metadata: Record<string, string | null> | null;
  title: string | null;
  description: string | null;
};

export type RawEditUploadStatus = {
  state: 'idle' | 'running' | 'succeeded' | 'failed';
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
};

export type RawEditUploadTriggerResponse = {
  accepted: boolean;
  status: RawEditUploadStatus;
  message?: string | null;
};

/**
 * 録画済みビデオのマッピング
 */
export function mapRecordedVideo(raw: RawRecordedVideo): RecordedVideo {
  return {
    id: raw.id,
    path: raw.path,
    filename: raw.filename,
    startedAt: raw.started_at ?? null,
    gameMode: raw.game_mode ?? null,
    match: raw.match ?? null,
    rule: raw.rule ?? null,
    stage: raw.stage ?? null,
    rate: raw.rate ?? null,
    judgement: raw.judgement ?? null,
    kill: normaliseNumber(raw.kill),
    death: normaliseNumber(raw.death),
    special: normaliseNumber(raw.special),
    allies: raw.allies ?? null,
    enemies: raw.enemies ?? null,
    hazard: normaliseNumber(raw.hazard),
    goldenEgg: normaliseNumber(raw.golden_egg),
    powerEgg: normaliseNumber(raw.power_egg),
    rescue: normaliseNumber(raw.rescue),
    rescued: normaliseNumber(raw.rescued),
    hasSubtitles: Boolean(raw.has_subtitle),
    hasThumbnail: Boolean(raw.has_thumbnail),
    durationSeconds: normaliseNumber(raw.duration_seconds, true),
    sizeBytes: normaliseNumber(raw.size_bytes, true),
  };
}

/**
 * 編集済みビデオのマッピング
 */
export function mapEditedVideo(raw: RawEditedVideo): EditedVideo {
  const metadataEntries = raw.metadata ?? {};
  const metadata: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(metadataEntries)) {
    metadata[key] = value ?? null;
  }
  return {
    id: raw.id,
    path: raw.path,
    filename: raw.filename,
    hasSubtitles: Boolean(raw.has_subtitle),
    hasThumbnail: Boolean(raw.has_thumbnail),
    durationSeconds: normaliseNumber(raw.duration_seconds, true),
    updatedAt: raw.updated_at ?? null,
    sizeBytes: normaliseNumber(raw.size_bytes, true),
    metadata,
    title: raw.title ?? null,
    description: raw.description ?? null,
  };
}

/**
 * 編集・アップロード状態のマッピング
 */
export function mapEditUploadStatus(raw: RawEditUploadStatus): EditUploadStatus {
  return {
    state: raw.state,
    startedAt: raw.started_at ?? null,
    finishedAt: raw.finished_at ?? null,
    error: raw.error ?? null,
  };
}

/**
 * 編集・アップロード開始レスポンスのマッピング
 */
export function mapEditUploadTrigger(raw: RawEditUploadTriggerResponse): EditUploadTriggerResponse {
  return {
    accepted: raw.accepted,
    status: mapEditUploadStatus(raw.status),
    message: raw.message ?? null,
  };
}

/**
 * 数値の正規化
 */
function normaliseNumber(
  value: number | string | null | undefined,
  allowFloat = false
): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number') {
    return Number.isNaN(value) ? null : value;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return null;
    }
    const parsed = allowFloat ? Number(trimmed) : parseInt(trimmed, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}
