<script lang="ts">
  import type { EditedVideo, EditedVideoSource } from '../../api/types';
  import VideoPlayerDialog from '../media/VideoPlayerDialog.svelte';
  import ThumbnailZoomDialog from '../media/ThumbnailZoomDialog.svelte';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import ConfirmDialog from '../../../common/components/ConfirmDialog.svelte';
  import { createVideoListActions } from './useVideoListActions.svelte';

  interface Props {
    videos?: EditedVideo[];
    isLoading?: boolean;
    onRefresh?: () => void;
    onModalOpen?: () => void;
    onModalClose?: () => void;
  }

  let {
    videos = $bindable([]),
    isLoading = false,
    onRefresh,
    onModalOpen,
    onModalClose,
  }: Props = $props();

  // EditedDataList 固有の状態（タイトル表示用）
  let _currentVideoTitle = $state('');

  const pendingPreviewTooltip = '現時点の録画済動画から作成した場合、この内容の編集動画になります';

  const videoItems = $derived(videos);

  function getThumbnailUrlForSource(source: 'edited' | 'recorded', filename: string): string {
    // ファイル名から拡張子を除去して .png を追加
    const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
    return `/thumbnails/${source}/${encodeURIComponent(nameWithoutExt)}.png`;
  }

  function getThumbnailUrl(video: EditedVideo): string {
    return getThumbnailUrlForSource(
      video.thumbnailSource,
      video.thumbnailFilename ?? video.filename
    );
  }

  function getVideoUrl(videoId: string, video?: EditedVideo): string {
    // videoIdはフルパスなので、そのまま使用
    if (video?.source === 'pending') {
      return '';
    }
    return `/videos/edited/${encodeURIComponent(videoId)}`;
  }

  // 共通アクション（モーダル管理・削除・画像エラー処理）
  const actions = createVideoListActions<EditedVideo>({
    getThumbnailUrl: (filename, video) =>
      getThumbnailUrlForSource(
        video?.thumbnailSource ?? 'edited',
        video?.thumbnailFilename ?? filename
      ),
    getVideoUrl,
    deleteVideo: async (video) => {
      const { deleteEditedVideo, deleteRecordedVideo } = await import('../../api/assets');
      if (video.source === 'pending') {
        await Promise.all(video.recordedVideoIds.map((videoId) => deleteRecordedVideo(videoId)));
        return;
      }
      await deleteEditedVideo(video.id);
    },
    getDeleteConfirmMessage: (video) => {
      if (video.source === 'pending') {
        return `「${video.filename}」に結合予定の録画済動画 ${video.recordedVideoIds.length} 件を削除してもよろしいですか？\nこの操作は取り消せません。`;
      }
      return `「${video.filename}」を削除してもよろしいですか？\nこの操作は取り消せません。`;
    },
    onRefresh: () => onRefresh?.(),
    onModalOpen: () => onModalOpen?.(),
    onModalClose: () => onModalClose?.(),
  });

  function getSourceLabel(source: EditedVideoSource): string {
    return source === 'pending' ? '編集プレビュー' : '編集済';
  }

  function getSourceTooltip(source: EditedVideoSource): string | undefined {
    return source === 'pending' ? pendingPreviewTooltip : undefined;
  }

  function handlePlayVideo(video: EditedVideo): void {
    if (!video.playable) {
      return;
    }
    // EditedDataList 固有: タイトル状態も更新する
    _currentVideoTitle = video.title ?? video.filename;
    actions.handlePlayVideo(video);
  }

  function handleZoomThumbnail(video: EditedVideo): void {
    // EditedDataList 固有: サムネイルファイル名を設定する
    const nameWithoutExt = video.filename.replace(/\.[^/.]+$/, '');
    _currentVideoTitle = `${nameWithoutExt}.png`;
    actions.handleZoomThumbnail(video);
  }
</script>

<div class="video-list glass-scroller">
  {#if isLoading && videoItems.length === 0}
    <div
      class="video-item glass-card loading-preview-card"
      data-testid="edited-video-loading-preview"
    >
      <div class="video-content">
        <div class="metadata-container">
          <div class="video-thumbnail-container">
            <div
              class="video-thumbnail loading-thumbnail"
              data-testid="edited-video-thumbnail-loading"
            >
              <span class="spinner-small" data-testid="edited-video-loading-spinner"></span>
              <span>サムネイル画像作成中</span>
            </div>
          </div>

          <div class="video-info">
            <div class="source-row">
              <span class="source-badge pending">編集プレビューを作成中</span>
            </div>
            <div class="info-item" data-testid="edited-video-title-loading">
              <span class="info-label">名称:</span>
              <span class="info-value loading-field">
                <span class="spinner-small" data-testid="edited-video-loading-spinner"></span>
                <span>動画の名称作成中</span>
              </span>
            </div>
            <div class="info-item" data-testid="edited-video-description-loading">
              <span class="info-label">説明:</span>
              <span class="info-value loading-field">
                <span class="spinner-small" data-testid="edited-video-loading-spinner"></span>
                <span>動画の説明作成中</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  {:else if videoItems.length === 0}
    <div class="empty-state glass-panel">
      <div class="empty-icon">📦</div>
      <p>編集データがありません</p>
    </div>
  {:else}
    {#each videoItems as video (`${video.source}:${video.id}`)}
      <div
        class="video-item glass-card"
        class:pending-candidate={video.source === 'pending'}
        data-testid="edited-video-item"
      >
        <!-- 削除ボタン (フローティング右上) -->
        <button
          class="delete-button glass-icon-button"
          data-testid="edited-video-delete-button"
          class:deleting={actions.deletingVideoId === video.id}
          disabled={actions.deletingVideoId === video.id}
          onclick={(e) => actions.handleDeleteVideo(e, video)}
          title={video.source === 'pending' ? '結合予定の録画済動画を削除' : '編集済動画を削除'}
        >
          {#if actions.deletingVideoId === video.id}
            <span class="spinner-small"></span>
          {:else}
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M3 6H5H21"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M10 11V17"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M14 11V17"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          {/if}
        </button>

        <div class="video-content">
          <!-- メタデータと字幕のコンテナ -->
          <div class="metadata-container">
            <!-- サムネイル -->
            <div class="video-thumbnail-container">
              <div class="video-thumbnail">
                <img
                  src={getThumbnailUrl(video)}
                  alt={video.filename}
                  onerror={actions.handleImageError}
                />
                <div class="thumbnail-overlay">
                  {#if video.playable}
                    <button
                      class="overlay-button play-button"
                      data-testid="edited-video-play-button"
                      onclick={() => handlePlayVideo(video)}
                      title="動画を再生"
                    >
                      <svg
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path d="M8 5V19L19 12L8 5Z" fill="currentColor" />
                      </svg>
                    </button>
                  {:else}
                    <span class="pending-video-label">動画未生成</span>
                  {/if}
                  <button
                    class="overlay-button zoom-button"
                    data-testid="edited-video-zoom-button"
                    onclick={() => handleZoomThumbnail(video)}
                    title="拡大表示"
                  >
                    <svg
                      width="24"
                      height="24"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M15 3H21V9M9 21H3V15M21 3L14 10M3 21L10 14"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            <!-- 動画情報 (タイトルと説明) -->
            <div class="video-info">
              <div class="source-row">
                <span
                  class="source-badge"
                  class:pending={video.source === 'pending'}
                  data-testid="edited-video-source-badge"
                  title={getSourceTooltip(video.source)}
                >
                  {getSourceLabel(video.source)}
                </span>
              </div>
              {#if video.title}
                <div class="info-item">
                  <span class="info-label">タイトル:</span>
                  <span class="info-value" data-testid="edited-video-title">{video.title}</span>
                </div>
              {/if}
              {#if video.description}
                <div class="info-item">
                  <span class="info-label">説明:</span>
                  <span class="info-value" data-testid="edited-video-description">
                    {video.description}
                  </span>
                </div>
              {/if}
              {#if !video.title && !video.description}
                <div class="info-item">
                  <span class="info-value-dim">タイトル・説明なし</span>
                </div>
              {/if}
            </div>

            <!-- 字幕情報 -->
            <div class="subtitle-info">
              <div class="metadata-row">
                <div class="metadata-item subtitle-item">
                  <span class="metadata-label">字幕:</span>
                  <span class="metadata-value" class:has-subtitles={video.hasSubtitles}>
                    {video.hasSubtitles ? '✓ あり' : '✗ なし'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    {/each}
  {/if}
</div>

<NotificationDialog
  isOpen={actions.showAlertDialog}
  variant={actions.alertVariant}
  message={actions.alertMessage}
  onClose={() => (actions.showAlertDialog = false)}
/>
<ConfirmDialog
  isOpen={actions.showConfirmDialog}
  message={actions.confirmMessage}
  confirmText="削除"
  onConfirm={actions.confirmDelete}
  onCancel={actions.cancelDelete}
/>

<!-- モーダル -->
<VideoPlayerDialog
  bind:visible={actions.showVideoPlayer}
  videoUrl={actions.currentVideoUrl}
  videoTitle="動画再生"
/>

<ThumbnailZoomDialog
  bind:visible={actions.showThumbnailZoom}
  imageUrl={actions.currentThumbnailUrl}
  imageTitle="サムネイル画像表示"
/>

<style>
  .video-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    width: 100%;
    flex: 1 1 auto;
    height: 100%;
    min-height: 0;
    overflow-y: auto;
    box-sizing: border-box;
  }

  .empty-state {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    width: 100%;
    min-width: 100%;
    box-sizing: border-box;
  }

  .empty-icon {
    font-size: 3rem;
    opacity: 0.5;
  }

  .empty-state p {
    margin: 0;
    font-size: 0.95rem;
    color: var(--text-secondary);
  }

  .video-item {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.25rem;
    width: 100%;
    box-sizing: border-box;
    flex: 0 0 auto;
    transition: box-shadow 0.25s ease;
  }

  .video-item:hover {
    box-shadow:
      0 10px 22px rgba(var(--theme-rgb-black), 0.24),
      0 0 12px rgba(var(--theme-rgb-accent), 0.12);
  }

  .video-item.pending-candidate {
    border-color: rgba(var(--theme-rgb-warning), 0.35);
  }

  .delete-button {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    width: 2.2rem;
    height: 2.2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: rgba(var(--theme-rgb-white), 0.72);
    padding: 0;
    transition: all 0.2s ease;
    opacity: 0;
    z-index: 10;
  }

  .video-item:hover .delete-button {
    opacity: 1;
  }

  .delete-button:hover {
    color: var(--theme-color-white);
    box-shadow: 0 6px 12px rgba(var(--theme-rgb-danger), 0.24);
    background: linear-gradient(
      145deg,
      rgba(var(--theme-rgb-danger), 0.92) 0%,
      rgba(var(--theme-rgb-red-dark), 0.85) 100%
    );
  }

  .delete-button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none !important;
  }

  .delete-button.deleting {
    opacity: 1;
  }

  .spinner-small {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(var(--theme-rgb-white), 0.3);
    border-top-color: var(--theme-color-white);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  .loading-preview-card {
    border-color: rgba(var(--theme-rgb-warning), 0.35);
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .video-content {
    display: block;
    --thumbnail-width: 280px;
  }

  .video-content::after {
    content: '';
    display: block;
    clear: both;
  }

  .metadata-container {
    display: block;
    min-width: 0;
  }

  .metadata-container::after {
    content: '';
    display: block;
    clear: both;
  }

  .video-thumbnail-container {
    float: right;
    width: min(var(--thumbnail-width), 100%);
    margin: 0.75rem 0.75rem 0.75rem 1rem;
  }

  .video-thumbnail {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    border-radius: 6px;
    overflow: hidden;
    background: rgba(var(--theme-rgb-black), 0.4);
  }

  .loading-thumbnail {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    color: var(--theme-status-warning);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .video-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .thumbnail-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(var(--theme-rgb-black), 0.5);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1rem;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .video-thumbnail:hover .thumbnail-overlay {
    opacity: 1;
  }

  .overlay-button {
    background: rgba(var(--theme-rgb-black), 0.6);
    border: 2px solid rgba(var(--theme-rgb-white), 0.8);
    border-radius: 50%;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
    color: var(--theme-color-white);
    padding: 0;
  }

  .overlay-button svg {
    width: 20px;
    height: 20px;
  }

  .overlay-button:hover {
    background: rgba(var(--theme-rgb-accent), 0.9);
    border-color: var(--accent-color);
    box-shadow: 0 4px 12px rgba(var(--theme-rgb-accent), 0.22);
  }

  .pending-video-label {
    border-radius: 999px;
    border: 1px solid rgba(var(--theme-rgb-warning), 0.6);
    background: rgba(var(--theme-rgb-black), 0.64);
    color: var(--theme-status-warning);
    font-size: 0.75rem;
    font-weight: 700;
    line-height: 1;
    padding: 0.55rem 0.75rem;
    white-space: nowrap;
  }

  /* 動画情報 (タイトル・説明) */
  .video-info {
    --info-label-width: 3.5rem;
    display: flow-root;
    font-size: 0.85rem;
    padding: 0 0.5rem 0.5rem;
    border-radius: 6px;
    text-align: left;
  }

  .source-row {
    display: flex;
    align-items: center;
    margin: 0 0 0.5rem;
  }

  .source-badge {
    border-radius: 999px;
    border: 1px solid rgba(var(--theme-rgb-accent), 0.45);
    background: rgba(var(--theme-rgb-accent), 0.12);
    color: var(--accent-color);
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1;
    padding: 0.3rem 0.55rem;
  }

  .source-badge.pending {
    border-color: rgba(var(--theme-rgb-warning), 0.55);
    background: rgba(var(--theme-rgb-warning), 0.12);
    color: var(--theme-status-warning);
  }

  .info-item {
    display: flex;
    flex-wrap: nowrap;
    align-items: flex-start;
    gap: 0.35rem;
    margin: 0 0 0.35rem;
  }

  .info-item:last-child {
    margin-bottom: 0;
  }

  .info-label {
    flex: 0 0 var(--info-label-width);
    width: var(--info-label-width);
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 0.8rem;
    white-space: nowrap;
  }

  .info-value {
    flex: 1 1 auto;
    min-width: 0;
    color: var(--accent-color);
    font-weight: 500;
    word-break: break-word;
    overflow-wrap: break-word;
    white-space: pre-wrap;
  }

  .loading-field {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--theme-status-warning);
  }

  .info-value-dim {
    color: rgba(var(--theme-rgb-orange-alt), 0.8);
    font-style: italic;
    font-size: 0.8rem;
  }

  /* 字幕情報 */
  .subtitle-info {
    --info-label-width: 3.5rem;
    display: flow-root;
    font-size: 0.85rem;
    border-top: 1px solid rgba(var(--theme-rgb-white), 0.1);
    margin-top: 0.35rem;
    padding: 0.75rem 0.5rem 0.5rem;
    border-radius: 6px;
    text-align: left;
  }

  .metadata-row {
    display: block;
  }

  .metadata-item {
    display: flex;
    flex-wrap: nowrap;
    gap: 0.35rem;
    align-items: flex-start;
  }

  .metadata-label {
    flex: 0 0 var(--info-label-width);
    width: var(--info-label-width);
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 0.8rem;
    white-space: nowrap;
  }

  .metadata-value {
    flex: 1 1 auto;
    min-width: 0;
    color: var(--accent-color);
    font-weight: 500;
    word-break: break-word;
    overflow-wrap: break-word;
  }

  /* 字幕情報アイテム */
  .subtitle-item .metadata-value.has-subtitles {
    color: var(--theme-status-success);
  }

  .subtitle-item .metadata-value:not(.has-subtitles) {
    color: rgba(var(--theme-rgb-orange-alt), 0.8);
  }

  /* スクロールバースタイル */
  .video-list::-webkit-scrollbar {
    width: 6px;
  }

  .video-list::-webkit-scrollbar-track {
    background: rgba(var(--theme-rgb-black), 0.2);
    border-radius: 3px;
  }

  .video-list::-webkit-scrollbar-thumb {
    background: rgba(var(--theme-rgb-accent), 0.3);
    border-radius: 3px;
  }

  .video-list::-webkit-scrollbar-thumb:hover {
    background: rgba(var(--theme-rgb-accent), 0.5);
  }

  @media (max-width: 1024px) {
    .video-list {
      min-height: clamp(3rem, 20vh, 6rem);
    }
  }

  @media (max-width: 750px) {
    .video-content {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    .video-content::after {
      content: none;
    }

    .video-thumbnail-container {
      float: none;
      align-self: flex-end;
      margin: 0 0 0.75rem;
    }
  }
</style>
