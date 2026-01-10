/**
 * Main API - Re-export
 *
 * 互換性維持のため、分割されたAPIをすべて再エクスポート
 */

// 型定義
export type {
  RecorderState,
  RecorderStateResponse,
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
} from './api/types';

// 録画制御API
export { startRecorder, getRecorderState } from './api/recording';

// アセットAPI
export {
  fetchRecordedVideos,
  fetchEditedVideos,
  startEditUploadProcess,
  fetchEditUploadStatus,
  deleteRecordedVideo,
  deleteEditedVideo,
} from './api/assets';

// メタデータ・字幕API
export {
  updateRecordedVideoMetadata,
  getRecordedSubtitle,
  updateRecordedSubtitle,
} from './api/metadata';
