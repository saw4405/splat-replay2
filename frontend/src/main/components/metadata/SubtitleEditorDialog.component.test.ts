import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SubtitleEditorDialog from './SubtitleEditorDialog.svelte';
import { getRecordedSubtitle } from '../../api/metadata';

vi.mock('../../api/metadata', () => ({
  getRecordedSubtitle: vi.fn(),
  updateRecordedSubtitle: vi.fn(),
}));

describe('SubtitleEditorDialog preview', () => {
  beforeEach(() => {
    vi.mocked(getRecordedSubtitle).mockResolvedValue({ blocks: [], video_duration: 30 });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('準備中と読み込み失敗を表示し、字幕プレビューを再試行できる', async () => {
    render(SubtitleEditorDialog, {
      props: {
        visible: true,
        videoId: 'recorded/test.mkv',
        videoUrl: '/video-preview/recorded.mp4?video_id=recorded%2Ftest.mkv',
      },
    });

    const video = await screen.findByLabelText('字幕プレビューを再生');
    expect(video).toHaveAttribute(
      'src',
      '/video-preview/recorded.mp4?video_id=recorded%2Ftest.mkv'
    );
    expect(screen.getByRole('status')).toHaveTextContent('動画プレビューを準備しています');

    await fireEvent.error(video);
    expect(screen.getByRole('alert')).toHaveTextContent('動画プレビューを読み込めませんでした');

    const load = vi.fn();
    Object.defineProperty(video, 'load', { value: load });
    await fireEvent.click(screen.getByRole('button', { name: '再試行' }));

    expect(load).toHaveBeenCalledOnce();
    expect(screen.getByRole('status')).toHaveTextContent('動画プレビューを準備しています');

    await fireEvent.canPlay(video);
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  });
});
