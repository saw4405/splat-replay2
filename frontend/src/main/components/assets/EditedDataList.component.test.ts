import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import EditedDataList from './EditedDataList.svelte';
import type { EditedVideo } from '../../api/types';

describe('EditedDataList', () => {
  const mockVideos: EditedVideo[] = [
    {
      id: 'edited_video1.mp4',
      path: '/path/to/edited_video1.mp4',
      filename: 'edited_video_1.mp4',
      hasSubtitles: false,
      hasThumbnail: true,
      durationSeconds: 180,
      updatedAt: '2026-03-14T10:30:00',
      sizeBytes: 2048000,
      metadata: {},
      title: null,
      description: null,
    },
    {
      id: 'edited_video2.mp4',
      path: '/path/to/edited_video2.mp4',
      filename: 'edited_video_2.mp4',
      hasSubtitles: false,
      hasThumbnail: true,
      durationSeconds: 200,
      updatedAt: '2026-03-14T11:30:00',
      sizeBytes: 3072000,
      metadata: {},
      title: null,
      description: null,
    },
  ];

  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.restoreAllMocks();
  });

  describe('リスト表示', () => {
    it('動画リストが空の場合、何も表示されない', () => {
      const { container } = render(EditedDataList, { props: { videos: [] } });
      expect(container.querySelector('.video-item')).not.toBeInTheDocument();
    });

    it('編集済み動画リストが表示される', () => {
      const { container } = render(EditedDataList, { props: { videos: mockVideos } });

      // ファイル名はaltテキストとして表示される
      const img1 = container.querySelector('img[alt="edited_video_1.mp4"]');
      const img2 = container.querySelector('img[alt="edited_video_2.mp4"]');
      expect(img1).toBeInTheDocument();
      expect(img2).toBeInTheDocument();
    });
  });

  describe('サムネイルURL生成', () => {
    it('サムネイルURLが正しく生成される', () => {
      const { container } = render(EditedDataList, { props: { videos: mockVideos } });

      const img = container.querySelector('img[alt*="edited_video_1"]') as HTMLImageElement;
      expect(img).toBeInTheDocument();
      expect(img.src).toContain('/thumbnails/edited/edited_video_1.png');
    });
  });

  describe('画像エラー処理', () => {
    it('画像読み込みエラー時にフォールバック画像が表示される', async () => {
      const { container } = render(EditedDataList, { props: { videos: mockVideos } });

      const img = container.querySelector('img') as HTMLImageElement;
      expect(img).toBeInTheDocument();

      const originalSrc = img.src;

      await fireEvent.error(img);

      // srcが変更されていることを確認
      expect(img.src).not.toBe(originalSrc);
      expect(img.src).toContain('data:image/svg+xml');
    });
  });

  describe('モーダル状態管理', () => {
    it('動画プレイヤーを開くとmodalOpenイベントが発火する', async () => {
      const modalOpenHandler = vi.fn();
      const { container } = render(EditedDataList, {
        props: { videos: mockVideos, onModalOpen: modalOpenHandler },
      });

      // オーバーレイ内の再生ボタンをクリック
      const playButton = container.querySelector('.play-button') as HTMLButtonElement;
      expect(playButton).toBeInTheDocument();
      await fireEvent.click(playButton);

      expect(modalOpenHandler).toHaveBeenCalled();
    });

    it('サムネイルズームを開くとmodalOpenイベントが発火する', async () => {
      const modalOpenHandler = vi.fn();
      const { container } = render(EditedDataList, {
        props: { videos: mockVideos, onModalOpen: modalOpenHandler },
      });

      // オーバーレイ内のズームボタンをクリック
      const zoomButton = container.querySelector('.zoom-button') as HTMLButtonElement;
      expect(zoomButton).toBeInTheDocument();
      await fireEvent.click(zoomButton);

      expect(modalOpenHandler).toHaveBeenCalled();
    });
  });

  describe('動画削除', () => {
    it('削除ボタンをクリックすると確認ダイアログが表示される', async () => {
      const { container } = render(EditedDataList, { props: { videos: mockVideos } });

      const deleteButton = container.querySelector('.delete-button') as HTMLButtonElement;
      expect(deleteButton).toBeInTheDocument();
      await fireEvent.click(deleteButton);

      // 確認メッセージを確認
      expect(screen.getByText(/edited_video_1\.mp4/)).toBeInTheDocument();
      expect(screen.getByText(/削除してもよろしいですか/)).toBeInTheDocument();
    });

    it('削除確認後に削除APIが呼ばれる', async () => {
      fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      const { container } = render(EditedDataList, { props: { videos: mockVideos } });

      // 削除ボタンをクリック
      const deleteButton = container.querySelector('.delete-button') as HTMLButtonElement;
      expect(deleteButton).toBeInTheDocument();
      await fireEvent.click(deleteButton);

      // 確認ダイアログの確認ボタンをクリック
      const confirmButton = screen.getByTestId('dialog-confirm-button');
      await fireEvent.click(confirmButton);

      // 削除APIが呼ばれることを確認（結果をテスト）
      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/assets/edited/edited_video1.mp4',
          expect.objectContaining({ method: 'DELETE' })
        );
      });
    });
  });
});
