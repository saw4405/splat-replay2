/**
 * インストーラーストアの単体テスト
 * 
 * Note: このテストを実行するには、テストフレームワーク（Vitest等）のセットアップが必要です。
 * 現在はテストの骨組みのみを提供しています。
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { get } from "svelte/store";
import {
  installationState,
  isLoading,
  error,
  progressInfo,
  fetchInstallationStatus,
  startInstallation,
  completeInstallation,
  goToNextStep,
  goToPreviousStep,
  skipCurrentStep,
  executeStep,
  checkSystem,
  clearError,
} from "./store";
import { InstallationStep } from "./types";

// グローバル fetch のモック
global.fetch = vi.fn();

describe("Installer Store", () => {
  beforeEach(() => {
    // 各テスト前にストアとモックをリセット
    installationState.set(null);
    isLoading.set(false);
    error.set(null);
    vi.clearAllMocks();
  });

  describe("fetchInstallationStatus", () => {
    it("should fetch and set installation status", async () => {
      const mockState = {
        is_completed: false,
        current_step: InstallationStep.HARDWARE_CHECK,
        completed_steps: [],
        skipped_steps: [],
        installation_date: null,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockState,
      });

      await fetchInstallationStatus();

      expect(get(installationState)).toEqual(mockState);
      expect(get(isLoading)).toBe(false);
      expect(get(error)).toBeNull();
    });

    it("should handle API errors", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ error: "Server error" }),
      });

      await fetchInstallationStatus();

      expect(get(error)).toEqual({ error: "Server error" });
      expect(get(isLoading)).toBe(false);
    });
  });

  describe("startInstallation", () => {
    it("should start installation and fetch status", async () => {
      const mockState = {
        is_completed: false,
        current_step: InstallationStep.HARDWARE_CHECK,
        completed_steps: [],
        skipped_steps: [],
        installation_date: null,
      };

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockState,
        });

      await startInstallation();

      expect(get(installationState)).toEqual(mockState);
    });
  });

  describe("completeInstallation", () => {
    it("should complete installation and update status", async () => {
      const mockState = {
        is_completed: true,
        current_step: InstallationStep.YOUTUBE_SETUP,
        completed_steps: [
          InstallationStep.HARDWARE_CHECK,
          InstallationStep.OBS_SETUP,
          InstallationStep.FFMPEG_SETUP,
          InstallationStep.TESSERACT_SETUP,
          InstallationStep.FONT_INSTALLATION,
          InstallationStep.YOUTUBE_SETUP,
        ],
        skipped_steps: [],
        installation_date: "2024-01-01T00:00:00Z",
      };

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockState,
        });

      await completeInstallation();

      expect(get(installationState)?.is_completed).toBe(true);
    });
  });

  describe("navigation", () => {
    it("should go to next step", async () => {
      const mockState = {
        is_completed: false,
        current_step: InstallationStep.OBS_SETUP,
        completed_steps: [InstallationStep.HARDWARE_CHECK],
        skipped_steps: [],
        installation_date: null,
      };

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockState,
        });

      await goToNextStep();

      expect(get(installationState)?.current_step).toBe(
        InstallationStep.OBS_SETUP
      );
    });

    it("should go to previous step", async () => {
      const mockState = {
        is_completed: false,
        current_step: InstallationStep.HARDWARE_CHECK,
        completed_steps: [],
        skipped_steps: [],
        installation_date: null,
      };

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockState,
        });

      await goToPreviousStep();

      expect(get(installationState)?.current_step).toBe(
        InstallationStep.HARDWARE_CHECK
      );
    });

    it("should skip current step", async () => {
      installationState.set({
        is_completed: false,
        current_step: InstallationStep.TESSERACT_SETUP,
        completed_steps: [
          InstallationStep.HARDWARE_CHECK,
          InstallationStep.OBS_SETUP,
          InstallationStep.FFMPEG_SETUP,
        ],
        skipped_steps: [],
        installation_date: null,
      });

      const mockState = {
        is_completed: false,
        current_step: InstallationStep.FONT_INSTALLATION,
        completed_steps: [
          InstallationStep.HARDWARE_CHECK,
          InstallationStep.OBS_SETUP,
          InstallationStep.FFMPEG_SETUP,
        ],
        skipped_steps: [InstallationStep.TESSERACT_SETUP],
        installation_date: null,
      };

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockState,
        });

      await skipCurrentStep();

      expect(get(installationState)?.skipped_steps).toContain(
        InstallationStep.TESSERACT_SETUP
      );
    });
  });

  describe("executeStep", () => {
    it("should execute a step and return result", async () => {
      const mockResult = {
        success: true,
        message: "Step completed successfully",
      };

      const mockState = {
        is_completed: false,
        current_step: InstallationStep.OBS_SETUP,
        completed_steps: [InstallationStep.HARDWARE_CHECK],
        skipped_steps: [],
        installation_date: null,
      };

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockResult,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockState,
        });

      const result = await executeStep(InstallationStep.HARDWARE_CHECK);

      expect(result).toEqual(mockResult);
    });
  });

  describe("checkSystem", () => {
    it("should check OBS installation", async () => {
      const mockResult = {
        is_installed: true,
        installation_path: "C:\\Program Files\\obs-studio",
        version: "30.0.0",
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      });

      const result = await checkSystem("obs");

      expect(result).toEqual(mockResult);
    });

    it("should check FFMPEG installation", async () => {
      const mockResult = {
        is_installed: false,
        installation_guide_url: "https://ffmpeg.org/download.html",
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      });

      const result = await checkSystem("ffmpeg");

      expect(result).toEqual(mockResult);
    });
  });

  describe("progressInfo", () => {
    it("should calculate progress correctly", () => {
      installationState.set({
        is_completed: false,
        current_step: InstallationStep.FFMPEG_SETUP,
        completed_steps: [
          InstallationStep.HARDWARE_CHECK,
          InstallationStep.OBS_SETUP,
        ],
        skipped_steps: [],
        installation_date: null,
      });

      const progress = get(progressInfo);

      expect(progress).toEqual({
        current_step_index: 2,
        total_steps: 6,
        percentage: 33, // 2/6 = 33%
        current_step_name: InstallationStep.FFMPEG_SETUP,
      });
    });

    it("should return null when state is not loaded", () => {
      installationState.set(null);

      const progress = get(progressInfo);

      expect(progress).toBeNull();
    });
  });

  describe("clearError", () => {
    it("should clear error state", () => {
      error.set({ error: "Test error" });

      clearError();

      expect(get(error)).toBeNull();
    });
  });
});
