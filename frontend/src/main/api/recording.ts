/**
 * 録画制御API
 *
 * 責務：
 * - 録画の開始・状態取得
 */

import type {
  RecorderPreviewMode,
  RecorderPreviewModeResponse,
  RecorderState,
  RecorderStateResponse,
} from './types.ts';
import { JSON_HEADERS, safeReadText } from './utils.ts';

/**
 * 録画を開始
 */
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

/**
 * 録画状態を取得
 */
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

/**
 * プレビュー入力種別を取得
 */
export async function getRecorderPreviewMode(): Promise<RecorderPreviewMode> {
  const response = await fetch('/api/recorder/preview-mode', {
    headers: JSON_HEADERS,
  });
  if (!response.ok) {
    const detail = await safeReadText(response);
    throw new Error(detail || 'Failed to fetch recorder preview mode');
  }
  const body: RecorderPreviewModeResponse = await response.json();
  return body.mode;
}
