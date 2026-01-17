/**
 * アセットAPI
 *
 * 責務：
 * - 録画済み・編集済みビデオの一覧取得
 * - ビデオの削除
 * - 編集・アップロードプロセスの制御
 */

import type {
  RecordedVideo,
  EditedVideo,
  EditUploadStatus,
  EditUploadTriggerResponse,
} from './types';
import { JSON_HEADERS, safeReadText } from './utils';
import {
  mapRecordedVideo,
  mapEditedVideo,
  mapEditUploadStatus,
  mapEditUploadTrigger,
} from './mappers';

/**
 * 録画済みビデオ一覧を取得
 */
export async function fetchRecordedVideos(): Promise<RecordedVideo[]> {
  const response = await fetch('/api/assets/recorded', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch recorded videos');
  }
  const body = await response.json();
  const videos: RecordedVideo[] = body.map(mapRecordedVideo);
  // 新しい順にソート (startedAt降順)
  videos.sort((a: RecordedVideo, b: RecordedVideo) => {
    if (!a.startedAt && !b.startedAt) return 0;
    if (!a.startedAt) return 1;
    if (!b.startedAt) return -1;
    return new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime();
  });
  return videos;
}

/**
 * 編集済みビデオ一覧を取得
 */
export async function fetchEditedVideos(): Promise<EditedVideo[]> {
  const response = await fetch('/api/assets/edited', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch edited videos');
  }
  const body = await response.json();
  const videos: EditedVideo[] = body.map(mapEditedVideo);
  // 新しい順にソート (updatedAt降順)
  videos.sort((a: EditedVideo, b: EditedVideo) => {
    if (!a.updatedAt && !b.updatedAt) return 0;
    if (!a.updatedAt) return 1;
    if (!b.updatedAt) return -1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
  return videos;
}

/**
 * 編集・アップロードプロセスを開始
 */
export async function startEditUploadProcess(options?: {
  auto?: boolean;
}): Promise<EditUploadTriggerResponse> {
  const params = new URLSearchParams();
  if (options?.auto) {
    params.set('auto', '1');
  }
  const url = params.toString()
    ? `/api/process/edit-upload?${params.toString()}`
    : '/api/process/edit-upload';
  const response = await fetch(url, {
    method: 'POST',
    headers: JSON_HEADERS,
  });
  const rawBody = await response.json();
  const mapped = mapEditUploadTrigger(rawBody);
  if (response.status !== 202 && response.status !== 409) {
    const detail = rawBody.message ?? (await safeReadText(response));
    throw new Error(detail || 'Failed to start edit/upload process');
  }
  return mapped;
}

/**
 * 編集・アップロードプロセスの状態を取得
 */
export async function fetchEditUploadStatus(): Promise<EditUploadStatus> {
  const response = await fetch('/api/process/status', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch edit/upload status');
  }
  const body = await response.json();
  return mapEditUploadStatus(body);
}

/**
 * 録画済みビデオを削除
 */
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

/**
 * 編集済みビデオを削除
 */
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
