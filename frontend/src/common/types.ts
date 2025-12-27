/**
 * 共通型定義
 */

export interface ApiError {
  error: string;
  error_code?: string;
  recovery_action?: string;
}
