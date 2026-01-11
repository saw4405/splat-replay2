/**
 * セットアップ状態管理 - ナビゲーション
 *
 * 責務：
 * - ステップ間の移動
 * - サブステップの状態管理
 * - ステップのスキップ・完了
 */

import { get } from 'svelte/store';
import type { SetupStep, SetupState, StepResult } from '../types';
import {
  API_BASE_URL,
  isLoading,
  error,
  setupState,
  fetchInstallationStatus,
  handleApiError,
  safeParseJson,
  STEP_SUBSTEP_COUNTS,
} from './state';

/**
 * ステップに対応するセッションストレージキーを取得
 */
function getSubstepStorageKey(step: SetupStep): string {
  const stepToKeyMap: Record<SetupStep, string> = {
    hardware_check: 'hardware_substep_index',
    obs_setup: 'obs_substep_index',
    ffmpeg_setup: 'ffmpeg_substep_index',
    tesseract_setup: 'tesseract_substep_index',
    font_installation: 'font_substep_index',
    transcription_setup: 'transcription_substep_index',
    youtube_setup: 'youtube_substep_index',
  };
  return stepToKeyMap[step];
}

/**
 * 指定したステップのサブステップインデックスをクリア
 */
function _clearStepSubstepIndex(step: SetupStep): void {
  if (typeof window === 'undefined') return;
  const key = getSubstepStorageKey(step);
  if (key) {
    console.log(`[SubstepStorage] Clearing substep index for ${step} (key: ${key})`);
    window.sessionStorage.removeItem(key);
  }
}

/**
 * すべてのステップのサブステップインデックスをクリア
 */
function clearAllSubstepSessionStorage(): void {
  if (typeof window === 'undefined') return;

  const substepKeys = [
    'hardware_substep_index',
    'obs_substep_index',
    'ffmpeg_substep_index',
    'tesseract_substep_index',
    'font_substep_index',
    'transcription_substep_index',
    'youtube_substep_index',
  ];

  console.log('[SubstepStorage] Clearing ALL substep indices');
  for (const key of substepKeys) {
    window.sessionStorage.removeItem(key);
  }
}

/**
 * 指定したステップのサブステップインデックスを設定
 */
function setStepSubstepIndex(step: SetupStep, index: number): void {
  if (typeof window === 'undefined') return;
  const key = getSubstepStorageKey(step);
  if (key) {
    console.log(`[SubstepStorage] Setting substep index for ${step} to ${index} (key: ${key})`);
    window.sessionStorage.setItem(key, index.toString());
  }
}

/**
 * 次のステップに進む
 */
export async function goToNextStep(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const currentState = get(setupState);
    console.log(`[Navigation] goToNextStep: current step = ${currentState?.current_step}`);

    const response = await fetch(`${API_BASE_URL}/setup/navigation/next`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    // 次のステップは必ず最初から開始するため、すべてのサブステップ記録をクリア
    clearAllSubstepSessionStorage();

    await fetchInstallationStatus();

    const newState = get(setupState);
    console.log(`[Navigation] goToNextStep: new step = ${newState?.current_step}`);
  } catch (err) {
    console.error('Failed to go to next step:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * 前のステップに戻る
 */
export async function goToPreviousStep(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const currentState = get(setupState);
    console.log(`[Navigation] goToPreviousStep: current step = ${currentState?.current_step}`);

    const response = await fetch(`${API_BASE_URL}/setup/navigation/previous`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    // レスポンスから新しい状態を取得
    const newState = await safeParseJson<SetupState>(response);
    const targetStep = newState.current_step;

    console.log(`[Navigation] goToPreviousStep: target step = ${targetStep}`);

    // 1. まずすべての履歴をクリア
    clearAllSubstepSessionStorage();

    // 2. 戻り先のステップだけ、最後のサブステップに設定
    if (targetStep) {
      const lastIndex = (STEP_SUBSTEP_COUNTS[targetStep] || 1) - 1;
      setStepSubstepIndex(targetStep, lastIndex);
    }

    // 3. 最後に状態を更新
    setupState.set(newState);
  } catch (err) {
    console.error('Failed to go to previous step:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * 現在のステップをスキップ
 */
export async function skipCurrentStep(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const state = get(setupState);
    if (!state) {
      throw new Error('Installation state not loaded');
    }

    const response = await fetch(`${API_BASE_URL}/setup/steps/${state.current_step}/skip`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error('Failed to skip step:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * ステップを完了してマーク
 */
export async function executeStep(step: SetupStep): Promise<StepResult> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/steps/${step}/complete`, {
      method: 'POST',
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    // ステップ完了後、状態を再取得
    await fetchInstallationStatus();

    // 成功レスポンスを返す
    return {
      success: true,
      message: 'Step completed successfully',
    };
  } catch (err) {
    console.error('Failed to complete step:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * サブステップを完了してマーク
 */
export async function markSubstepCompleted(
  step: SetupStep,
  substepId: string,
  completed: boolean = true
): Promise<void> {
  // バックグラウンドで実行するため、ローディング状態は変更しない
  try {
    const response = await fetch(
      `${API_BASE_URL}/setup/steps/${step}/substeps/${substepId}?completed=${completed}`,
      {
        method: 'POST',
      }
    );
    if (!response.ok) {
      console.error('Failed to mark substep completed');
      return;
    }

    // サブステップの状態を更新した後、インストール状態を再取得
    await fetchInstallationStatus();
  } catch (err) {
    console.error('Failed to mark substep completed:', err);
  }
}
