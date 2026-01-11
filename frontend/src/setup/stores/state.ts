/**
 * セットアップ状態管理 - 基本状態ストア
 *
 * 責務：
 * - セットアップ状態の保持
 * - ローディング・エラー状態の管理
 * - 進行状況の計算
 */

import { writable, derived } from 'svelte/store';
import type { SetupState, ProgressInfo, ApiError } from '../types';

// API ベース URL
// 開発環境: 空文字列（Viteプロキシが /api を http://127.0.0.1:8000 に転送）
// 本番環境: 空文字列（WebViewが同一オリジンで提供）
export const API_BASE_URL =
  (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL || '';

// セットアップ状態ストア
export const setupState = writable<SetupState | null>(null);

// ローディング状態
export const isLoading = writable<boolean>(false);

// エラー状態
export const error = writable<ApiError | null>(null);

// 各ステップのサブステップ数を定義
export const STEP_SUBSTEP_COUNTS: Record<string, number> = {
  hardware_check: 5, // ハードウェアチェック: 5つのタスク
  obs_setup: 7, // OBS: 7つのサブステップ
  ffmpeg_setup: 1, // FFMPEG: 1つのサブステップ
  tesseract_setup: 2, // Tesseract: 2つのサブステップ
  font_installation: 2, // Font: 2つのサブステップ
  transcription_setup: 4, // 文字起こし: 4つのサブステップ
  youtube_setup: 7, // YouTube: 7つのサブステップ
};

// 進行状況の計算（サブステップを含む）
export const progressInfo = derived(setupState, ($state): ProgressInfo | null => {
  if (!$state) return null;

  const steps = [
    'hardware_check',
    'obs_setup',
    'ffmpeg_setup',
    'tesseract_setup',
    'font_installation',
    'transcription_setup',
    'youtube_setup',
  ];

  const currentIndex = steps.indexOf($state.current_step);

  // 総サブステップ数を計算
  const totalSubsteps = steps.reduce((sum, step) => sum + (STEP_SUBSTEP_COUNTS[step] || 1), 0);

  // 完了したサブステップ数を計算
  let completedSubsteps = 0;

  // 完了済みステップのサブステップをすべてカウント
  for (const completedStep of $state.completed_steps) {
    completedSubsteps += STEP_SUBSTEP_COUNTS[completedStep] || 1;
  }

  // 現在のステップの完了済みサブステップをカウント
  if (currentIndex >= 0 && !$state.completed_steps.includes($state.current_step)) {
    const currentStepDetails = $state.step_details[$state.current_step] || {};
    const completedSubstepsInCurrentStep = Object.values(currentStepDetails).filter(
      (completed) => completed === true
    ).length;
    completedSubsteps += completedSubstepsInCurrentStep;
  }

  const percentage = Math.round((completedSubsteps / totalSubsteps) * 100);

  return {
    current_step_index: currentIndex,
    total_steps: steps.length,
    percentage,
    current_step_name: $state.current_step,
    completed_substeps: completedSubsteps,
    total_substeps: totalSubsteps,
  };
});

/**
 * API エラーハンドリング
 */
export async function handleApiError(response: Response): Promise<never> {
  let errorData: ApiError;
  try {
    errorData = await response.json();
  } catch {
    errorData = {
      error: `HTTP Error: ${response.status} ${response.statusText}`,
    };
  }
  error.set(errorData);
  throw new Error(errorData.error);
}

/**
 * レスポンスから安全にJSONをパース
 * JSONパースエラーが発生した場合は適切なエラーメッセージを返す
 */
export async function safeParseJson<T>(response: Response): Promise<T> {
  const text = await response.text();

  if (!text || text.trim() === '') {
    throw new Error(`Empty response from ${response.url}`);
  }

  try {
    return JSON.parse(text) as T;
  } catch (err) {
    console.error('Failed to parse JSON:', {
      url: response.url,
      status: response.status,
      statusText: response.statusText,
      contentType: response.headers.get('content-type'),
      body: text.substring(0, 200), // 最初の200文字のみログ
    });
    throw new Error(
      `Invalid JSON response from ${response.url}: ${err instanceof Error ? err.message : 'Unknown error'}`
    );
  }
}

/**
 * エラーをクリア
 */
export function clearError(): void {
  error.set(null);
}

/**
 * インストール状態を取得
 */
export async function fetchInstallationStatus(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/status`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await safeParseJson<SetupState>(response);
    setupState.set(data);
  } catch (err) {
    console.error('Failed to fetch installation status:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * インストーラーを開始
 */
export async function startInstallation(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/start`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error('Failed to start installation:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * インストールを完了
 */
export async function completeInstallation(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/complete`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error('Failed to complete installation:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}
