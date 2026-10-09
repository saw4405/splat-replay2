import { describe, expect, it } from 'vitest';
import { getClientPlatform } from '../../../setup/platform';
import { getVideoUrl } from './videoUrl';

describe('getVideoUrl', () => {
  it('macOS は MKV を MP4 preview URL にする', () => {
    expect(getVideoUrl('recorded', 'recorded/match.mkv', 'macos')).toBe(
      '/video-preview/recorded.mp4?video_id=recorded%2Fmatch.mkv'
    );
  });

  it('macOS の MP4 は既存動画 URL を使う', () => {
    expect(getVideoUrl('edited', 'edited/match.mp4', 'macos')).toBe(
      '/videos/edited/edited%2Fmatch.mp4'
    );
  });

  it('Windows の MKV は既存動画 URL を使う', () => {
    expect(getVideoUrl('edited', 'edited/match.mkv', 'windows')).toBe(
      '/videos/edited/edited%2Fmatch.mkv'
    );
  });

  it('動画の互換性判定には閲覧端末のOSを使う', () => {
    expect(getVideoUrl('recorded', 'recorded/match.mkv', getClientPlatform('MacIntel'))).toBe(
      '/video-preview/recorded.mp4?video_id=recorded%2Fmatch.mkv'
    );
  });
});
