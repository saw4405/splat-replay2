/**
 * セットアップ関連の型定義
 */

// 共通型は common/types.ts からインポート
export type { ApiError } from '../common/types';

export enum SetupStep {
  HARDWARE_CHECK = 'hardware_check',
  FFMPEG_SETUP = 'ffmpeg_setup',
  OBS_SETUP = 'obs_setup',
  TESSERACT_SETUP = 'tesseract_setup',
  FONT_INSTALLATION = 'font_installation',
  TRANSCRIPTION_SETUP = 'transcription_setup',
  YOUTUBE_SETUP = 'youtube_setup',
}

export interface SetupState {
  is_completed: boolean;
  current_step: SetupStep;
  completed_steps: SetupStep[];
  skipped_steps: SetupStep[];
  step_details: Record<string, Record<string, boolean>>;
  installation_date: string | null;
}

export interface StepResult {
  success: boolean;
  message: string;
  details?: Record<string, unknown>;
  next_action?: string;
}

export interface SystemCheckResult {
  is_installed: boolean;
  installation_path?: string;
  version?: string;
  installation_guide_url?: string;
  error_message?: string;
}

export interface MessageResponse {
  message: string;
}

export interface ProgressInfo {
  current_step_index: number;
  total_steps: number;
  percentage: number;
  current_step_name: string;
  completed_substeps: number;
  total_substeps: number;
}
