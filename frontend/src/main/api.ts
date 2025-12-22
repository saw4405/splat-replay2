const JSON_HEADERS: HeadersInit = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
};

export type RecorderState = 'stopped' | 'recording' | 'paused';

export interface PreviewFrameResponse {
  has_frame: boolean;
  image_data_url: string | null;
  timestamp: number | null;
}

export interface RecorderStateResponse {
  state: RecorderState;
}

export type EditUploadState = 'idle' | 'running' | 'succeeded' | 'failed';

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

// Progress Event Types
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

export async function startRecorder(): Promise<void> {
  const response = await fetch('/api/recorder/start', {
    method: 'POST',
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to start auto recorder');
  }
}

export async function getRecorderState(): Promise<RecorderState> {
  const response = await fetch('/api/recorder/state', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch recorder state');
  }
  const body: RecorderStateResponse = await response.json();
  return body.state;
}

export async function getPreviewFrame(): Promise<PreviewFrameResponse> {
  const response = await fetch('/api/preview/latest', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch preview frame');
  }
  return response.json() as Promise<PreviewFrameResponse>;
}

export async function fetchRecordedVideos(): Promise<RecordedVideo[]> {
  const response = await fetch('/api/assets/recorded', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch recorded videos');
  }
  const body = (await response.json()) as RawRecordedVideo[];
  const videos = body.map(mapRecordedVideo);
  // 新しい順にソート (startedAt降順)
  videos.sort((a, b) => {
    if (!a.startedAt && !b.startedAt) return 0;
    if (!a.startedAt) return 1;
    if (!b.startedAt) return -1;
    return new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime();
  });
  return videos;
}

export async function fetchEditedVideos(): Promise<EditedVideo[]> {
  const response = await fetch('/api/assets/edited', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch edited videos');
  }
  const body = (await response.json()) as RawEditedVideo[];
  const videos = body.map(mapEditedVideo);
  // 新しい順にソート (updatedAt降順)
  videos.sort((a, b) => {
    if (!a.updatedAt && !b.updatedAt) return 0;
    if (!a.updatedAt) return 1;
    if (!b.updatedAt) return -1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
  return videos;
}

export async function startEditUploadProcess(): Promise<EditUploadTriggerResponse> {
  const response = await fetch('/api/process/edit-upload', {
    method: 'POST',
    headers: JSON_HEADERS,
  });
  const rawBody = (await response.json()) as RawEditUploadTriggerResponse;
  const mapped = mapEditUploadTrigger(rawBody);
  if (response.status !== 202 && response.status !== 409) {
    const detail = rawBody.message ?? (await safeReadText(response));
    throw new Error(detail || 'Failed to start edit/upload process');
  }
  return mapped;
}

export async function fetchEditUploadStatus(): Promise<EditUploadStatus> {
  const response = await fetch('/api/process/status', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch edit/upload status');
  }
  const body = (await response.json()) as RawEditUploadStatus;
  return mapEditUploadStatus(body);
}

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

export async function updateRecordedVideoMetadata(
  videoId: string,
  metadata: MetadataUpdate
): Promise<RecordedVideo> {
  const response = await fetch(`/api/assets/recorded/${encodeURIComponent(videoId)}/metadata`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify(metadata),
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to update metadata');
  }
  const body = (await response.json()) as RawRecordedVideo;
  return mapRecordedVideo(body);
}

export async function getRecordedSubtitle(videoId: string): Promise<SubtitleData> {
  const response = await fetch(`/api/subtitles/recorded/${encodeURIComponent(videoId)}`, {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch subtitle');
  }
  return (await response.json()) as SubtitleData;
}

export async function updateRecordedSubtitle(
  videoId: string,
  data: SubtitleData
): Promise<SubtitleData> {
  const response = await fetch(`/api/subtitles/recorded/${encodeURIComponent(videoId)}`, {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to update subtitle');
  }
  return (await response.json()) as SubtitleData;
}

export async function deleteRecordedVideo(videoId: string): Promise<void> {
  const response = await fetch(`/api/assets/recorded/${encodeURIComponent(videoId)}`, {
    method: 'DELETE',
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to delete recorded video');
  }
}

export async function deleteEditedVideo(videoId: string): Promise<void> {
  const response = await fetch(`/api/assets/edited/${encodeURIComponent(videoId)}`, {
    method: 'DELETE',
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to delete edited video');
  }
}

type RawRecordedVideo = {
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

type RawEditedVideo = {
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

type RawEditUploadStatus = {
  state: EditUploadState;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
};

type RawEditUploadTriggerResponse = {
  accepted: boolean;
  status: RawEditUploadStatus;
  message?: string | null;
};

function mapRecordedVideo(raw: RawRecordedVideo): RecordedVideo {
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

function mapEditedVideo(raw: RawEditedVideo): EditedVideo {
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

function mapEditUploadStatus(raw: RawEditUploadStatus): EditUploadStatus {
  return {
    state: raw.state,
    startedAt: raw.started_at ?? null,
    finishedAt: raw.finished_at ?? null,
    error: raw.error ?? null,
  };
}

function mapEditUploadTrigger(raw: RawEditUploadTriggerResponse): EditUploadTriggerResponse {
  return {
    accepted: raw.accepted,
    status: mapEditUploadStatus(raw.status),
    message: raw.message ?? null,
  };
}

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

async function safeReadText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return '';
  }
}
