import { getClientPlatform, type SetupPlatform } from '../../../setup/platform';

export type VideoKind = 'recorded' | 'edited';

export function getVideoUrl(
  kind: VideoKind,
  videoId: string,
  platform: SetupPlatform = getClientPlatform()
): string {
  if (platform === 'macos' && videoId.toLowerCase().endsWith('.mkv')) {
    return `/video-preview/${kind}.mp4?${new URLSearchParams({ video_id: videoId })}`;
  }

  return `/videos/${kind}/${encodeURIComponent(videoId)}`;
}
