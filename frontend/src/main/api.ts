/**
 * Main API - Re-export
 *
 * 互換性維持のため、分割されたAPIをすべて再エクスポート
 */

// 型定義
export type {
  RecorderState,
  RecorderStateResponse,
  AutoRecorderState,
  AutoRecorderStateResponse,
  SwitchPowerState,
  EditUploadState,
  EditUploadStatus,
  EditUploadTriggerResponse,
  RecordedVideo,
  EditedVideo,
  MetadataUpdate,
  SubtitleBlock,
  SubtitleData,
  ProgressEventKind,
  ProgressEvent,
} from './api/types.ts';
// 録画制御API
export { startRecorder, getRecorderState, getAutoRecorderState } from './api/recording.ts';

// アセットAPI
export {
  fetchRecordedVideos,
  fetchEditedVideos,
  startEditUploadProcess,
  fetchEditUploadStatus,
  deleteRecordedVideo,
  deleteEditedVideo,
  cancelEditUploadProcess,
} from './api/assets.ts';

// メタデータ・字幕API
export {
  updateRecordedVideoMetadata,
  getRecordedSubtitle,
  updateRecordedSubtitle,
} from './api/metadata.ts';

import { processApi } from './api/process.ts';

export const api = {
  process: processApi,
};
