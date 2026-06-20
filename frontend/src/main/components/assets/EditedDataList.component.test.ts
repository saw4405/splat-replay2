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
      source: 'edited',
      playable: true,
      recordedVideoIds: [],
      thumbnailSource: 'edited',
      thumbnailFilename: null,
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
      source: 'edited',
      playable: true,
      recordedVideoIds: [],
      thumbnailSource: 'edited',
      thumbnailFilename: null,
    },
  ];

  const mockPendingVideos: EditedVideo[] = [
    {
      id: 'pending/20260314_12_Xマッチ_ガチエリア',
      path: '',
      filename: '20260314_12_Xマッチ_ガチエリア.mp4',
      hasSubtitles: false,
      hasThumbnail: true,
      durationSeconds: null,
      updatedAt: '2026-03-14T12:30:00',
      sizeBytes: 4096000,
      metadata: {
        schedule: '2026-03-14T12:00:00',
        recorded_count: '2',
      },
      title: 'Xマッチ / ガチエリア / キンメダイ美術館',
      description: 'WIN / 8K/3D / SP×2',
      source: 'pending',
      playable: false,
      recordedVideoIds: ['recorded/recorded_video_1.mp4', 'recorded/recorded_video_2.mp4'],
      thumbnailSource: 'edited',
      thumbnailFilename: '20260314_12_Xマッチ_ガチエリア.mp4',
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
      render(EditedDataList, { props: { videos: [] } });
      expect(screen.queryByTestId('edited-video-item')).not.toBeInTheDocument();
    });

    it('編集済み動画リストが表示される', () => {
      render(EditedDataList, { props: { videos: mockVideos } });

      // ファイル名はaltテキストとして表示される
      const img1 = screen.getByAltText('edited_video_1.mp4');
      const img2 = screen.getByAltText('edited_video_2.mp4');
      expect(img1).toBeInTheDocument();
      expect(img2).toBeInTheDocument();
    });

    it('結合予定の録画済動画グループを編集プレビューとして表示する', () => {
      const { container } = render(EditedDataList, {
        props: { videos: mockPendingVideos },
      });

      const sourceBadge = screen.getByTestId('edited-video-source-badge');
      expect(sourceBadge).toHaveTextContent('編集プレビュー');
      expect(sourceBadge).toHaveAttribute(
        'title',
        '現時点の録画済動画から作成した場合、この内容の編集動画になります'
      );
      expect(
        screen.queryByText('現時点の録画済動画から作成すると、この内容の編集動画になります。')
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('edited-video-title')).toHaveTextContent(
        'Xマッチ / ガチエリア / キンメダイ美術館'
      );
      expect(screen.getByTestId('edited-video-description')).toHaveTextContent('WIN');
      expect(screen.getByTestId('edited-video-description')).toHaveTextContent('8K/3D');
      expect(screen.getByTestId('edited-video-description')).toHaveTextContent('SP×2');

      expect(screen.queryByTestId('edited-video-play-button')).not.toBeInTheDocument();

      const img = screen.getByAltText('20260314_12_Xマッチ_ガチエリア.mp4') as HTMLImageElement;
      expect(img).toBeInTheDocument();
      expect(img.src).toContain(
        '/thumbnails/edited/20260314_12_X%E3%83%9E%E3%83%83%E3%83%81_%E3%82%AC%E3%83%81%E3%82%A8%E3%83%AA%E3%82%A2.png'
      );
    });

    it('編集済動画と録画済動画の種別バッジを区別して表示する', () => {
      render(EditedDataList, {
        props: { videos: [...mockVideos.slice(0, 1), ...mockPendingVideos] },
      });

      const badges = screen.getAllByTestId('edited-video-source-badge');
      expect(badges.map((badge) => badge.textContent)).toEqual(['編集済', '編集プレビュー']);
    });

    it('編集プレビュー作成中はサムネイル・名称・説明の各表示箇所にローディングを表示する', () => {
      render(EditedDataList, {
        props: { videos: [], isLoading: true },
      });

      expect(screen.getByTestId('edited-video-loading-preview')).toHaveTextContent(
        '編集プレビューを作成中'
      );
      expect(screen.getByTestId('edited-video-thumbnail-loading')).toHaveTextContent(
        'サムネイル画像作成中'
      );
      expect(screen.getByTestId('edited-video-title-loading')).toHaveTextContent(
        '動画の名称作成中'
      );
      expect(screen.getByTestId('edited-video-description-loading')).toHaveTextContent(
        '動画の説明作成中'
      );
      expect(screen.getAllByTestId('edited-video-loading-spinner')).toHaveLength(3);
      expect(screen.queryByText('編集済データがありません')).not.toBeInTheDocument();
    });
  });

  describe('サムネイルURL生成', () => {
    it('サムネイルURLが正しく生成される', () => {
      render(EditedDataList, { props: { videos: mockVideos } });

      const img = screen.getByAltText(/edited_video_1/) as HTMLImageElement;
      expect(img).toBeInTheDocument();
      expect(img.src).toContain('/thumbnails/edited/edited_video_1.png');
    });
  });

  describe('画像エラー処理', () => {
    it('画像読み込みエラー時にフォールバック画像が表示される', async () => {
      render(EditedDataList, { props: { videos: mockVideos } });

      const img = screen.getByAltText('edited_video_1.mp4') as HTMLImageElement;
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
      render(EditedDataList, {
        props: { videos: mockVideos, onModalOpen: modalOpenHandler },
      });

      // オーバーレイ内の再生ボタンをクリック
      const playButton = screen.getAllByTestId('edited-video-play-button')[0] as HTMLButtonElement;
      expect(playButton).toBeInTheDocument();
      await fireEvent.click(playButton);

      expect(modalOpenHandler).toHaveBeenCalled();
    });

    it('サムネイルズームを開くとmodalOpenイベントが発火する', async () => {
      const modalOpenHandler = vi.fn();
      render(EditedDataList, {
        props: { videos: mockVideos, onModalOpen: modalOpenHandler },
      });

      // オーバーレイ内のズームボタンをクリック
      const zoomButton = screen.getAllByTestId('edited-video-zoom-button')[0] as HTMLButtonElement;
      expect(zoomButton).toBeInTheDocument();
      await fireEvent.click(zoomButton);

      expect(modalOpenHandler).toHaveBeenCalled();
    });
  });

  describe('動画削除', () => {
    it('削除ボタンをクリックすると確認ダイアログが表示される', async () => {
      render(EditedDataList, { props: { videos: mockVideos } });

      const deleteButton = screen.getAllByTestId(
        'edited-video-delete-button'
      )[0] as HTMLButtonElement;
      expect(deleteButton).toBeInTheDocument();
      await fireEvent.click(deleteButton);

      // 確認メッセージを確認
      expect(screen.getByText(/edited_video_1\.mp4/)).toBeInTheDocument();
      expect(screen.getByText(/削除してもよろしいですか/)).toBeInTheDocument();
    });

    it('削除確認後に削除APIが呼ばれる', async () => {
      fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      render(EditedDataList, { props: { videos: mockVideos } });

      // 削除ボタンをクリック
      const deleteButton = screen.getAllByTestId(
        'edited-video-delete-button'
      )[0] as HTMLButtonElement;
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

    it('未生成グループの削除では結合予定の録画済動画を削除する', async () => {
      fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      render(EditedDataList, {
        props: { videos: mockPendingVideos },
      });

      const deleteButton = screen.getAllByTestId(
        'edited-video-delete-button'
      )[0] as HTMLButtonElement;
      expect(deleteButton).toBeInTheDocument();
      await fireEvent.click(deleteButton);

      expect(screen.getByText(/結合予定の録画済動画 2 件を削除/)).toBeInTheDocument();

      const confirmButton = screen.getByTestId('dialog-confirm-button');
      await fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/assets/recorded/recorded%2Frecorded_video_1.mp4',
          expect.objectContaining({ method: 'DELETE' })
        );
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/assets/recorded/recorded%2Frecorded_video_2.mp4',
          expect.objectContaining({ method: 'DELETE' })
        );
      });
    });
  });
});
