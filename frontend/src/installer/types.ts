/**
 * インストーラー関連の型定義
 */

export enum InstallationStep {
  HARDWARE_CHECK = 'hardware_check',
  FFMPEG_SETUP = 'ffmpeg_setup',
  OBS_SETUP = 'obs_setup',
  TESSERACT_SETUP = 'tesseract_setup',
  FONT_INSTALLATION = 'font_installation',
  YOUTUBE_SETUP = 'youtube_setup',
}

export interface InstallationState {
  is_completed: boolean;
  current_step: InstallationStep;
  completed_steps: InstallationStep[];
  skipped_steps: InstallationStep[];
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

export interface ProgressInfo {
  current_step_index: number;
  total_steps: number;
  percentage: number;
  current_step_name: string;
  completed_substeps: number;
  total_substeps: number;
}

export interface ApiError {
  error: string;
  error_code?: string;
  recovery_action?: string;
}
