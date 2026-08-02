import type { TaskState } from './progressStateMachine';

export type ResponsiveStage = 'editing' | 'waiting' | 'uploading';

export function pickResponsiveStage(
  editTask: TaskState | undefined,
  uploadTask: TaskState | undefined,
  waitingCount: number
): ResponsiveStage {
  const uploadStatus = uploadTask?.status;
  if (uploadStatus === 'running' || uploadStatus === 'failed' || uploadStatus === 'succeeded') {
    return 'uploading';
  }

  const editStatus = editTask?.status;
  if (editStatus === 'running' || editStatus === 'failed') {
    return 'editing';
  }

  if (waitingCount > 0) {
    return 'waiting';
  }

  return 'editing';
}
