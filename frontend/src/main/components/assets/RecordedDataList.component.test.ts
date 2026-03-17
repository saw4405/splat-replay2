import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import RecordedDataList from './RecordedDataList.svelte';
import type { RecordedVideo } from '../../api/types';
import { clearMetadataOptionsCache } from '../../api/metadata';

describe('RecordedDataList', () => {
  const mockVideos: RecordedVideo[] = [
    {
      id: 'video1.mp4',
      path: '/path/to/video1.mp4',
      filename: 'test_video_1.mp4',
      startedAt: '2026-03-14T10:00:00',
      gameMode: null,
      match: null,
      rule: null,
      stage: null,
      rate: null,
      judgement: null,
      kill: null,
      death: null,
      special: null,
      goldMedals: null,
      silverMedals: null,
      allies: null,
      enemies: null,
      hazard: null,
      goldenEgg: null,
      powerEgg: null,
      rescue: null,
      rescued: null,
      hasSubtitles: false,
      hasThumbnail: true,
      durationSeconds: 300,
      sizeBytes: 1024000,
    },
    {
      id: 'video2.mp4',
      path: '/path/to/video2.mp4',
      filename: 'test_video_2.mp4',
      startedAt: '2026-03-14T11:00:00',
      gameMode: null,
      match: null,
      rule: null,
      stage: null,
      rate: null,
      judgement: null,
      kill: null,
      death: null,
      special: null,
      goldMedals: null,
      silverMedals: null,
      allies: null,
      enemies: null,
      hazard: null,
      goldenEgg: null,
      powerEgg: null,
      rescue: null,
      rescued: null,
      hasSubtitles: false,
      hasThumbnail: true,
      durationSeconds: null,
      sizeBytes: null,
    },
  ];

  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // メタデータオプションのキャッシュをクリア
    clearMetadataOptionsCache();

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
      const { container } = render(RecordedDataList, { props: { videos: [] } });
      expect(container.querySelector('.video-item')).not.toBeInTheDocument();
    });

    it('動画リストが表示される', () => {
      const { container } = render(RecordedDataList, { props: { videos: mockVideos } });

      // ファイル名はaltテキストとして表示される
      const img1 = container.querySelector('img[alt="test_video_1.mp4"]');
      const img2 = container.querySelector('img[alt="test_video_2.mp4"]');
      expect(img1).toBeInTheDocument();
      expect(img2).toBeInTheDocument();
    });

    it('タイムスタンプがフォーマットされて表示される', () => {
      render(RecordedDataList, { props: { videos: mockVideos } });

      // タイムスタンプのフォーマット: YYYY/MM/DD HH:MM:SS
      expect(screen.getByText(/2026\/03\/14 10:00:00/)).toBeInTheDocument();
    });

    it('startedAtがnullの場合「未開始」と表示される', () => {
      const videosWithNullStart: RecordedVideo[] = [{ ...mockVideos[0], startedAt: null }];
      render(RecordedDataList, { props: { videos: videosWithNullStart } });

      expect(screen.getByText('未開始')).toBeInTheDocument();
    });
  });

  describe('サムネイルURL生成', () => {
    it('サムネイルURLが正しく生成される', () => {
      const { container } = render(RecordedDataList, { props: { videos: mockVideos } });

      const img = container.querySelector('img[alt*="test_video_1"]') as HTMLImageElement;
      expect(img).toBeInTheDocument();
      expect(img.src).toContain('/thumbnails/recorded/test_video_1.png');
    });
  });

  describe('画像エラー処理', () => {
    it('画像読み込みエラー時にフォールバック画像が表示される', async () => {
      const { container } = render(RecordedDataList, { props: { videos: mockVideos } });

      const img = container.querySelector('img') as HTMLImageElement;
      expect(img).toBeInTheDocument();

      const originalSrc = img.src;

      // エラーイベントを発生させる
      await fireEvent.error(img);

      // srcが変更されていることを確認
      expect(img.src).not.toBe(originalSrc);
      expect(img.src).toContain('data:image/svg+xml');
    });
  });

  describe('モーダル状態管理', () => {
    it('メタデータエリアをクリックするとメタデータダイアログが表示される', async () => {
      fetchMock.mockResolvedValue(
        new Response(
          JSON.stringify({
            game_modes: [],
            matches: [],
            rules: [],
            stages: [],
            judgements: [],
          }),
          { status: 200 }
        )
      );

      render(RecordedDataList, { props: { videos: mockVideos } });

      // メタデータエリアをクリック（最初のビデオアイテム）
      const metadataButtons = screen.getAllByTestId('recorded-video-metadata-button');
      await fireEvent.click(metadataButtons[0]);

      // メタデータダイアログが表示されることを確認（結果をテスト）
      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toBeInTheDocument();
        expect(screen.getByText('メタデータ編集')).toBeInTheDocument();
      });
    });
  });

  describe('動画削除', () => {
    it('削除ボタンをクリックすると確認ダイアログが表示される', async () => {
      const { container } = render(RecordedDataList, { props: { videos: mockVideos } });

      const deleteButton = container.querySelector('.delete-button') as HTMLButtonElement;
      expect(deleteButton).toBeInTheDocument();
      await fireEvent.click(deleteButton);

      // 確認メッセージを確認
      expect(screen.getByText(/test_video_1\.mp4/)).toBeInTheDocument();
      expect(screen.getByText(/削除してもよろしいですか/)).toBeInTheDocument();
    });
  });
});
