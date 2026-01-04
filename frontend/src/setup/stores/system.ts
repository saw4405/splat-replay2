/**
 * セットアップ状態管理 - システムチェック・セットアップ
 *
 * 責務：
 * - 外部ソフトウェアのチェック
 * - FFmpeg/Tesseractのセットアップ
 */

import type { SystemCheckResult } from '../types';
import { API_BASE_URL, isLoading, error, handleApiError, safeParseJson } from './state';

/**
 * システムチェックを実行
 */
export async function checkSystem(
  software: 'obs' | 'ffmpeg' | 'tesseract' | 'font' | 'youtube' | 'ndi'
): Promise<SystemCheckResult> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/system/check/${software}`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<SystemCheckResult>(response);
    return result;
  } catch (err) {
    console.error(`Failed to check ${software}:`, err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * FFMPEGのセットアップを実行
 */
export async function setupFFMPEG(): Promise<SystemCheckResult> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/system/setup/ffmpeg`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<SystemCheckResult>(response);
    return result;
  } catch (err) {
    console.error('Failed to setup FFMPEG:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * Tesseractのセットアップを実行
 */
export async function setupTesseract(): Promise<SystemCheckResult> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/system/setup/tesseract`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<SystemCheckResult>(response);
    return result;
  } catch (err) {
    console.error('Failed to setup Tesseract:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}
