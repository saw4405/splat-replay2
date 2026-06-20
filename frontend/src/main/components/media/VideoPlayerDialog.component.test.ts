import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import VideoPlayerDialog from './VideoPlayerDialog.svelte';

describe('VideoPlayerDialog', () => {
  it('ビデオURLとタイトルが設定される', () => {
    render(VideoPlayerDialog, {
      props: {
        visible: true,
        videoUrl: '/api/videos/test.mp4',
        videoTitle: 'テスト動画',
      },
    });

    expect(screen.queryByText('テスト動画')).toBeInTheDocument();
  });

  it('ビデオ要素が正しいソースURLを持つ', () => {
    render(VideoPlayerDialog, {
      props: {
        visible: true,
        videoUrl: '/api/videos/test.mp4',
        videoTitle: 'テスト動画',
      },
    });

    const video = screen.getByLabelText('テスト動画を再生');
    expect(video).toHaveAttribute('src', '/api/videos/test.mp4');
    expect(video).toHaveAttribute('controls');
  });

  it('visibleがfalseの場合、ダイアログは表示されない', () => {
    render(VideoPlayerDialog, {
      props: {
        visible: false,
        videoUrl: '/api/videos/test.mp4',
        videoTitle: 'テスト動画',
      },
    });

    expect(screen.queryByText('テスト動画')).not.toBeInTheDocument();
  });

  it('閉じるボタンでダイアログが閉じる', async () => {
    render(VideoPlayerDialog, {
      props: {
        visible: true,
        videoUrl: '/api/videos/test.mp4',
        videoTitle: 'テスト動画',
      },
    });

    const closeButtons = screen.getAllByRole('button');
    const closeButton = closeButtons.find((btn) => {
      const ariaLabel = btn.getAttribute('aria-label');
      return ariaLabel === 'Close' || ariaLabel === '閉じる';
    });

    expect(closeButton).toBeDefined();
    if (closeButton) {
      await fireEvent.click(closeButton);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    }
  });
});
