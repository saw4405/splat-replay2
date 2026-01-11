/**
 * セットアップ状態管理 - Re-export
 *
 * 互換性維持のため、分割されたストアをすべて再エクスポート
 */

// 基本状態管理
export {
  setupState,
  isLoading,
  error,
  progressInfo,
  clearError,
  fetchInstallationStatus,
  startInstallation,
  completeInstallation,
} from './stores/state';

// ナビゲーション
export {
  goToNextStep,
  goToPreviousStep,
  skipCurrentStep,
  executeStep,
  markSubstepCompleted,
} from './stores/navigation';

// システムチェック・セットアップ
export { checkSystem, setupFFMPEG, setupTesseract } from './stores/system';

// 設定管理
export {
  getOBSConfig,
  saveOBSWebSocketPassword,
  listVideoDevices,
  listMicrophones,
  saveCaptureDevice,
  saveYouTubePrivacyStatus,
  getTranscriptionConfig,
  saveTranscriptionConfig,
} from './stores/config';
