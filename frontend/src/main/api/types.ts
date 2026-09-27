/**
 * API型定義
 *
 * 責務：
 * - バックエンドAPIとの通信で使用する型定義
 */

// 録画制御
export type RecorderState = 'STOPPED' | 'RECORDING' | 'PAUSED';
export type RecorderPreviewMode = 'live_capture' | 'video_file';
export type AutoRecorderState = 'idle' | 'running' | 'stopped';
export type SwitchPowerState =
  | 'unknown'
  | 'armed'
  | 'waiting_for_power_on'
  | 'capture_disconnected'
  | 'stopped';

export interface RecorderStateResponse {
  state: RecorderState;
}

export interface RecorderPreviewModeResponse {
  mode: RecorderPreviewMode;
}

export interface AutoRecorderStateResponse {
  state: AutoRecorderState;
  power_state: SwitchPowerState;
}

// 編集・アップロード
export type EditUploadState =
  | 'idle'
  | 'running'
  | 'cancelling'
  | 'cancelled'
  | 'succeeded'
  | 'failed';

export interface EditUploadStatus {
  state: EditUploadState;
  startedAt: string | null;
  finishedAt: string | null;
  error: string | null;
  sleepAfterUploadDefault: boolean;
  sleepAfterUploadEffective: boolean;
  sleepAfterUploadOverridden: boolean;
}

export interface EditUploadTriggerResponse {
  accepted: boolean;
  status: EditUploadStatus;
  message: string | null;
}

// アセット
export type EditedVideoSource = 'edited' | 'pending';
export type EditedVideoThumbnailSource = 'edited' | 'recorded';

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
  goldMedals: number | null;
  silverMedals: number | null;
  allies: string[] | null;
  enemies: string[] | null;
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
  source: EditedVideoSource;
  playable: boolean;
  recordedVideoIds: string[];
  thumbnailSource: EditedVideoThumbnailSource;
  thumbnailFilename: string | null;
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
  startedAt?: string;
  match?: string;
  rule?: string;
  stage?: string;
  rate?: string;
  judgement?: string;
  kill?: number;
  death?: number;
  special?: number;
  goldMedals?: number;
  silverMedals?: number;
  allies?: string[];
  enemies?: string[];
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

// 対戦履歴
export interface BattleHistoryEntry {
  record_id: string;
  source_video_id: string;
  game_mode: string;
  started_at: string | null;
  match: string | null;
  rule: string | null;
  stage: string | null;
  judgement: string | null;
  kill: number | null;
  death: number | null;
  special: number | null;
  assist: number | null;
  gold_medals: number | null;
  silver_medals: number | null;
  session_rate: string | null;
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

export interface VideoAssetPayload {
  video_id: string;
  duration_seconds: number;
  judgement: string;
  stage_name: string;
  kill: number;
  death: number;
  special: number;
  gold_medals: number;
  silver_medals: number;
  rate: { type: string; value: string } | null;
}

export interface GroupPayload {
  group_index: number;
  date_label: string;
  match_name: string;
  rule_name: string;
  thumbnail_filename?: string | null;
  video_assets: VideoAssetPayload[];
}

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
  progress_percent: number | null;
  clips: GroupPayload[] | null;
}
