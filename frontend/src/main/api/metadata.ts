/**
 * メタデータ・字幕API
 *
 * 責務：
 * - ビデオメタデータの更新
 * - 字幕データの取得・更新
 */

import type { RecordedVideo, MetadataUpdate, SubtitleData } from './types';
import { JSON_HEADERS, safeReadText } from './utils';
import { mapRecordedVideo } from './mappers';

/**
 * 録画済みビデオのメタデータを更新
 */
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
  const body = await response.json();
  return mapRecordedVideo(body);
}

/**
 * 録画済みビデオの字幕を取得
 */
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

/**
 * 録画済みビデオの字幕を更新
 */
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
