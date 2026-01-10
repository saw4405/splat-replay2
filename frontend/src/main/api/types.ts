/**
 * API型定義
 *
 * 責務：
 * - バックエンドAPIとの通信で使用する型定義
 */

// 録画制御
export type RecorderState = 'stopped' | 'recording' | 'paused';

export interface RecorderStateResponse {
  state: RecorderState;
}

// 編集・アップロード
export type EditUploadState = 'idle' | 'running' | 'succeeded' | 'failed';

export interface EditUploadStatus {
  state: EditUploadState;
  startedAt: string | null;
  finishedAt: string | null;
  error: string | null;
}

export interface EditUploadTriggerResponse {
  accepted: boolean;
  status: EditUploadStatus;
  message: string | null;
}

// アセット
export interface RecordedVideo {
  id: string;
  path: string;
  filename: string;
  startedAt: string | null;
  gameMode: string | null;
  match: string | null;
  rule: string | null;
  stage: string | null;
  rate: string | null;
  judgement: string | null;
  kill: number | null;
  death: number | null;
  special: number | null;
  hazard: number | null;
  goldenEgg: number | null;
  powerEgg: number | null;
  rescue: number | null;
  rescued: number | null;
  hasSubtitles: boolean;
  hasThumbnail: boolean;
  durationSeconds: number | null;
  sizeBytes: number | null;
}

export interface EditedVideo {
  id: string;
  path: string;
  filename: string;
  hasSubtitles: boolean;
  hasThumbnail: boolean;
  durationSeconds: number | null;
  updatedAt: string | null;
  sizeBytes: number | null;
  metadata: Record<string, string | null>;
  title: string | null;
  description: string | null;
}

// メタデータ・字幕
export interface MetadataUpdate {
  match?: string;
  rule?: string;
  stage?: string;
  rate?: string;
  judgement?: string;
  kill?: number;
  death?: number;
  special?: number;
}

export interface MetadataOptionItem {
  key: string;
  label: string;
}

export interface MetadataOptions {
  gameModes: MetadataOptionItem[];
  matches: MetadataOptionItem[];
  rules: MetadataOptionItem[];
  stages: MetadataOptionItem[];
  judgements: MetadataOptionItem[];
}

export interface SubtitleBlock {
  index: number;
  start_time: number; // 秒単位
  end_time: number; // 秒単位
  text: string;
}

export interface SubtitleData {
  blocks: SubtitleBlock[];
  video_duration: number | null;
}

// 進捗イベント
export type ProgressEventKind =
  | 'start'
  | 'total'
  | 'stage'
  | 'advance'
  | 'finish'
  | 'items'
  | 'item_stage'
  | 'item_finish';

export interface ProgressEvent {
  task_id: string;
  kind: ProgressEventKind;
  task_name: string;
  total: number | null;
  completed: number | null;
  stage_key: string | null;
  stage_label: string | null;
  stage_index: number | null;
  stage_count: number | null;
  success: boolean | null;
  message: string | null;
  items: string[] | null;
  item_index: number | null;
  item_key: string | null;
  item_label: string | null;
}
