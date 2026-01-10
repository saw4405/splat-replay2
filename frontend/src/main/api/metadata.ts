/**
 * メタデータ・字幕API
 *
 * 責務：
 * - ビデオメタデータの更新
 * - 字幕データの取得・更新
 */

import type {
  RecordedVideo,
  MetadataUpdate,
  MetadataOptionItem,
  MetadataOptions,
  SubtitleData,
} from './types';
import { JSON_HEADERS, safeReadText } from './utils';
import { mapRecordedVideo } from './mappers';

type RawMetadataOptionItem = {
  key: string;
  label: string;
};

type RawMetadataOptionsResponse = {
  game_modes: RawMetadataOptionItem[];
  matches: RawMetadataOptionItem[];
  rules: RawMetadataOptionItem[];
  stages: RawMetadataOptionItem[];
  judgements: RawMetadataOptionItem[];
};

let metadataOptionsCache: MetadataOptions | null = null;
let metadataOptionsPromise: Promise<MetadataOptions> | null = null;

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

function mapMetadataOptions(raw: RawMetadataOptionsResponse): MetadataOptions {
  return {
    gameModes: raw.game_modes ?? [],
    matches: raw.matches ?? [],
    rules: raw.rules ?? [],
    stages: raw.stages ?? [],
    judgements: raw.judgements ?? [],
  };
}

export function buildMetadataOptionMap(
  options: MetadataOptions
): Record<keyof MetadataOptions, Record<string, string>> {
  const toMap = (items: MetadataOptionItem[]): Record<string, string> =>
    items.reduce<Record<string, string>>((acc, item) => {
      acc[item.key] = item.label;
      return acc;
    }, {});

  return {
    gameModes: toMap(options.gameModes),
    matches: toMap(options.matches),
    rules: toMap(options.rules),
    stages: toMap(options.stages),
    judgements: toMap(options.judgements),
  };
}

export async function getMetadataOptions(): Promise<MetadataOptions> {
  if (metadataOptionsCache) {
    return metadataOptionsCache;
  }
  if (metadataOptionsPromise) {
    return metadataOptionsPromise;
  }
  metadataOptionsPromise = (async () => {
    try {
      const response = await fetch('/api/metadata/options', {
        headers: JSON_HEADERS,
      });
      if (!response.ok) {
        const detail = await safeReadText(response);
        throw new Error(detail || 'Failed to fetch metadata options');
      }
      const body = (await response.json()) as RawMetadataOptionsResponse;
      const options = mapMetadataOptions(body);
      metadataOptionsCache = options;
      metadataOptionsPromise = null;
      return options;
    } catch (error) {
      metadataOptionsPromise = null;
      throw error;
    }
  })();
  return metadataOptionsPromise;
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
