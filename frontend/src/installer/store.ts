/**
 * インストーラー状態管理ストア
 */

import { writable, derived, get } from "svelte/store";
import type {
  InstallationState,
  InstallationStep,
  StepResult,
  SystemCheckResult,
  ProgressInfo,
  ApiError,
} from "./types";

// API ベース URL
const API_BASE_URL = "http://localhost:8000";

// インストール状態ストア
export const installationState = writable<InstallationState | null>(null);

// ローディング状態
export const isLoading = writable<boolean>(false);

// エラー状態
export const error = writable<ApiError | null>(null);

// 各ステップのサブステップ数を定義
const STEP_SUBSTEP_COUNTS: Record<string, number> = {
  hardware_check: 5, // ハードウェアチェック: 5つのタスク
  obs_setup: 6, // OBS: 6つのサブステップ
  ffmpeg_setup: 1, // FFMPEG: 1つのサブステップ
  tesseract_setup: 2, // Tesseract: 2つのサブステップ
  font_installation: 2, // Font: 2つのサブステップ
  youtube_setup: 5, // YouTube: 5つのサブステップ
};

// 進行状況の計算（サブステップを含む）
export const progressInfo = derived(
  installationState,
  ($state): ProgressInfo | null => {
    if (!$state) return null;

    const steps = [
      "hardware_check",
      "obs_setup",
      "ffmpeg_setup",
      "tesseract_setup",
      "font_installation",
      "youtube_setup",
    ];

    const currentIndex = steps.indexOf($state.current_step);

    // 総サブステップ数を計算
    const totalSubsteps = steps.reduce(
      (sum, step) => sum + (STEP_SUBSTEP_COUNTS[step] || 1),
      0
    );

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
  }
);

/**
 * API エラーハンドリング
 */
async function handleApiError(response: Response): Promise<never> {
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
 * インストール状態を取得
 */
export async function fetchInstallationStatus(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/installer/status`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const data: InstallationState = await response.json();
    installationState.set(data);
  } catch (err) {
    console.error("Failed to fetch installation status:", err);
    if (err instanceof Error && !get(error)) {
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
    const response = await fetch(`${API_BASE_URL}/installer/start`, {
      method: "POST",
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error("Failed to start installation:", err);
    if (err instanceof Error && !get(error)) {
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
    const response = await fetch(`${API_BASE_URL}/installer/complete`, {
      method: "POST",
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error("Failed to complete installation:", err);
    if (err instanceof Error && !get(error)) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * 次のステップに進む
 */
export async function goToNextStep(): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/installer/navigation/next`, {
      method: "POST",
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error("Failed to go to next step:", err);
    if (err instanceof Error && !get(error)) {
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
    const response = await fetch(
      `${API_BASE_URL}/installer/navigation/previous`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error("Failed to go to previous step:", err);
    if (err instanceof Error && !get(error)) {
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
    const state = get(installationState);
    if (!state) {
      throw new Error("Installation state not loaded");
    }

    const response = await fetch(
      `${API_BASE_URL}/installer/steps/${state.current_step}/skip`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      await handleApiError(response);
    }

    await fetchInstallationStatus();
  } catch (err) {
    console.error("Failed to skip step:", err);
    if (err instanceof Error && !get(error)) {
      error.set({ error: err.message });
    }
  } finally {
    isLoading.set(false);
  }
}

/**
 * ステップを完了としてマーク
 */
export async function executeStep(step: InstallationStep): Promise<StepResult> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(
      `${API_BASE_URL}/installer/steps/${step}/complete`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      await handleApiError(response);
    }

    // ステップ完了後、状態を再取得
    await fetchInstallationStatus();

    // 成功レスポンスを返す
    return {
      success: true,
      message: "Step completed successfully",
    };
  } catch (err) {
    console.error("Failed to complete step:", err);
    if (err instanceof Error && !get(error)) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * サブステップを完了としてマーク
 */
export async function markSubstepCompleted(
  step: InstallationStep,
  substepId: string,
  completed: boolean = true
): Promise<void> {
  // バックグラウンドで実行するため、ローディング状態は変更しない
  try {
    const response = await fetch(
      `${API_BASE_URL}/installer/steps/${step}/substeps/${substepId}?completed=${completed}`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      console.error("Failed to mark substep completed");
      return;
    }

    // サブステップの状態を更新した後、インストール状態を再取得
    await fetchInstallationStatus();
  } catch (err) {
    console.error("Failed to mark substep completed:", err);
  }
}

/**
 * システムチェックを実行
 */
export async function checkSystem(
  software: "obs" | "ffmpeg" | "tesseract" | "font" | "youtube" | "ndi"
): Promise<SystemCheckResult> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/installer/system/check/${software}`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const result: SystemCheckResult = await response.json();
    return result;
  } catch (err) {
    console.error(`Failed to check ${software}:`, err);
    if (err instanceof Error && !get(error)) {
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
    const response = await fetch(`${API_BASE_URL}/installer/system/setup/ffmpeg`, {
      method: "POST",
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result: SystemCheckResult = await response.json();
    return result;
  } catch (err) {
    console.error("Failed to setup FFMPEG:", err);
    if (err instanceof Error && !get(error)) {
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
    const response = await fetch(`${API_BASE_URL}/installer/system/setup/tesseract`, {
      method: "POST",
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result: SystemCheckResult = await response.json();
    return result;
  } catch (err) {
    console.error("Failed to setup Tesseract:", err);
    if (err instanceof Error && !get(error)) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * エラーをクリア
 */
export function clearError(): void {
  error.set(null);
}
