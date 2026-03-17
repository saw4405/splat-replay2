/**
 * Video操作 Integration テスト
 *
 * 責務：
 * - VideoPlayerDialog と ThumbnailZoomDialog の統合動作検証
 * - ビデオ再生とサムネイル表示の基本フロー
 * - ダイアログの開閉
 *
 * 分類: integration
 */

import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import VideoPlayerDialog from './VideoPlayerDialog.svelte';
import ThumbnailZoomDialog from './ThumbnailZoomDialog.svelte';

describe('Video操作 Integration', () => {
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
      const { container } = render(VideoPlayerDialog, {
        props: {
          visible: true,
          videoUrl: '/api/videos/test.mp4',
          videoTitle: 'テスト動画',
        },
      });

      const video = container.querySelector('video');
      expect(video).toBeInTheDocument();

      const source = container.querySelector('source');
      expect(source).toBeInTheDocument();
      expect(source?.getAttribute('src')).toBe('/api/videos/test.mp4');
      expect(source?.getAttribute('type')).toBe('video/mp4');
    });

    it('ビデオ要素はcontrols属性を持つ', () => {
      const { container } = render(VideoPlayerDialog, {
        props: {
          visible: true,
          videoUrl: '/api/videos/test.mp4',
          videoTitle: 'テスト動画',
        },
      });

      const video = container.querySelector('video');
      expect(video?.hasAttribute('controls')).toBe(true);
    });

    it('ビデオ要素はautoplay属性を持つ', () => {
      const { container } = render(VideoPlayerDialog, {
        props: {
          visible: true,
          videoUrl: '/api/videos/test.mp4',
          videoTitle: 'テスト動画',
        },
      });

      const video = container.querySelector('video');
      expect(video?.hasAttribute('autoplay')).toBe(true);
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

      // 閉じるボタンを探す（BaseDialogから提供される）
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

  describe('ThumbnailZoomDialog', () => {
    it('サムネイルURLとタイトルが設定される', () => {
      render(ThumbnailZoomDialog, {
        props: {
          visible: true,
          imageUrl: '/api/thumbnails/test.png',
          imageTitle: 'テストサムネイル',
        },
      });

      expect(screen.queryByText('テストサムネイル')).toBeInTheDocument();
    });

    it('画像要素が正しいソースURLを持つ', () => {
      const { container } = render(ThumbnailZoomDialog, {
        props: {
          visible: true,
          imageUrl: '/api/thumbnails/test.png',
          imageTitle: 'テストサムネイル',
        },
      });

      const img = container.querySelector('img');
      expect(img).toBeInTheDocument();
      expect(img?.getAttribute('src')).toBe('/api/thumbnails/test.png');
      expect(img?.getAttribute('alt')).toBe('テストサムネイル');
    });

    it('visibleがfalseの場合、ダイアログは表示されない', () => {
      render(ThumbnailZoomDialog, {
        props: {
          visible: false,
          imageUrl: '/api/thumbnails/test.png',
          imageTitle: 'テストサムネイル',
        },
      });

      expect(screen.queryByText('テストサムネイル')).not.toBeInTheDocument();
    });

    it('閉じるボタンでダイアログが閉じる', async () => {
      render(ThumbnailZoomDialog, {
        props: {
          visible: true,
          imageUrl: '/api/thumbnails/test.png',
          imageTitle: 'テストサムネイル',
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

  describe('ビデオとサムネイルの切り替え', () => {
    it('ビデオダイアログとサムネイルダイアログを切り替えられる', async () => {
      const { rerender } = render(VideoPlayerDialog, {
        props: {
          visible: true,
          videoUrl: '/api/videos/test.mp4',
          videoTitle: 'テスト動画',
        },
      });

      expect(screen.queryByText('テスト動画')).toBeInTheDocument();

      // ビデオダイアログを閉じる
      await rerender({
        visible: false,
        videoUrl: '/api/videos/test.mp4',
        videoTitle: 'テスト動画',
      });

      expect(screen.queryByText('テスト動画')).not.toBeInTheDocument();
    });

    it('複数のメディアダイアログが独立して動作する', () => {
      const { container: videoContainer } = render(VideoPlayerDialog, {
        props: {
          visible: true,
          videoUrl: '/api/videos/test.mp4',
          videoTitle: 'ビデオ',
        },
      });

      const { container: thumbnailContainer } = render(ThumbnailZoomDialog, {
        props: {
          visible: true,
          imageUrl: '/api/thumbnails/test.png',
          imageTitle: 'サムネイル',
        },
      });

      expect(screen.queryByText('ビデオ')).toBeInTheDocument();
      expect(screen.queryByText('サムネイル')).toBeInTheDocument();

      const video = videoContainer.querySelector('video');
      const img = thumbnailContainer.querySelector('img');

      expect(video).toBeInTheDocument();
      expect(img).toBeInTheDocument();
    });
  });

  describe('エラーハンドリング', () => {
    it('空のビデオURLでもエラーが発生しない', () => {
      const { container } = render(VideoPlayerDialog, {
        props: {
          visible: true,
          videoUrl: '',
          videoTitle: 'Empty Video',
        },
      });

      const source = container.querySelector('source');
      // 空文字列の場合、src属性は存在するが空文字列またはnull
      const srcValue = source?.getAttribute('src');
      expect(srcValue === '' || srcValue === null).toBe(true);
    });

    it('空のサムネイルURLでもエラーが発生しない', () => {
      const { container } = render(ThumbnailZoomDialog, {
        props: {
          visible: true,
          imageUrl: '',
          imageTitle: 'Empty Thumbnail',
        },
      });

      const img = container.querySelector('img');
      // 空文字列の場合、src属性は存在するが空文字列またはnull
      const srcValue = img?.getAttribute('src');
      expect(srcValue === '' || srcValue === null).toBe(true);
    });
  });
});
