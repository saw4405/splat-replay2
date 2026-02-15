<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { EditedVideo } from '../../api/types';
  import VideoPlayerDialog from '../media/VideoPlayerDialog.svelte';
  import ThumbnailZoomDialog from '../media/ThumbnailZoomDialog.svelte';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import ConfirmDialog from '../../../common/components/ConfirmDialog.svelte';

  export let videos: EditedVideo[] = [];

  const dispatch = createEventDispatcher();

  let showVideoPlayer = false;
  let showThumbnailZoom = false;
  let showAlertDialog = false;
  let showConfirmDialog = false;
  let alertMessage = '';
  let alertVariant: 'info' | 'success' | 'warning' | 'error' = 'info';
  let confirmMessage = '';
  let pendingDeleteVideo: EditedVideo | null = null;
  let currentVideoUrl = '';
  let currentThumbnailUrl = '';
  let _currentVideoTitle = '';
  let wasModalOpen = false; // モーダルが開いていたかどうかを追跡
  let deletingVideoId: string | null = null; // 削除中の動画ID

  // モーダルの開閉状態を監視
  $: {
    const isAnyModalOpen =
      showVideoPlayer || showThumbnailZoom || showAlertDialog || showConfirmDialog;

    if (isAnyModalOpen && !wasModalOpen) {
      // モーダルが開いた
      dispatch('modalOpen');
      wasModalOpen = true;
    } else if (!isAnyModalOpen && wasModalOpen) {
      // モーダルが閉じた
      dispatch('modalClose');
      wasModalOpen = false;
    }
  }

  function getThumbnailUrl(filename: string): string {
    // ファイル名から拡張子を除去して .png を追加
    const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
    return `/api/thumbnails/edited/${encodeURIComponent(nameWithoutExt)}.png`;
  }

  function getVideoUrl(videoId: string): string {
    // videoIdはフルパスなので、そのまま使用
    return `/api/videos/edited/${encodeURIComponent(videoId)}`;
  }

  function handleImageError(e: Event): void {
    const img = e.currentTarget as HTMLImageElement;
    img.src =
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='90'%3E%3Crect fill='%23333' width='160' height='90'/%3E%3Ctext fill='%23666' x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='12'%3ENo Image%3C/text%3E%3C/svg%3E";
  }

  function handlePlayVideo(video: EditedVideo): void {
    currentVideoUrl = getVideoUrl(video.id); // フルパスを使用
    _currentVideoTitle = video.filename;
    showVideoPlayer = true;
  }

  function handleZoomThumbnail(video: EditedVideo): void {
    currentThumbnailUrl = getThumbnailUrl(video.filename);
    // サムネイルファイル名を設定
    const nameWithoutExt = video.filename.replace(/\.[^/.]+$/, '');
    _currentVideoTitle = `${nameWithoutExt}.png`;
    showThumbnailZoom = true;
  }

  async function handleDeleteVideo(event: MouseEvent, video: EditedVideo): Promise<void> {
    event.stopPropagation();

    confirmMessage = `「${video.filename}」を削除してもよろしいですか？\nこの操作は取り消せません。`;
    pendingDeleteVideo = video;
    showConfirmDialog = true;
  }

  async function confirmDelete(): Promise<void> {
    if (!pendingDeleteVideo) return;

    const video = pendingDeleteVideo;
    deletingVideoId = video.id;
    showConfirmDialog = false;
    pendingDeleteVideo = null;

    try {
      const { deleteEditedVideo } = await import('../../api/assets');
      await deleteEditedVideo(video.id);
      console.log('Video deleted successfully:', video.id);

      // ビデオリストを再読み込み
      dispatch('refresh');
    } catch (error) {
      console.error('Failed to delete video:', error);
      alertMessage = `動画の削除に失敗しました: ${error}`;
      alertVariant = 'error';
      showAlertDialog = true;
    } finally {
      deletingVideoId = null;
    }
  }

  function cancelDelete(): void {
    showConfirmDialog = false;
    pendingDeleteVideo = null;
  }
</script>

<div class="video-list glass-scroller">
  {#if videos.length === 0}
    <div class="empty-state glass-panel">
      <div class="empty-icon">📦</div>
      <p>編集済データはありません</p>
    </div>
  {:else}
    {#each videos as video (video.id)}
      <div class="video-item glass-card">
        <!-- 削除ボタン (フローティング右上) -->
        <button
          class="delete-button glass-icon-button"
          class:deleting={deletingVideoId === video.id}
          disabled={deletingVideoId === video.id}
          on:click={(e) => handleDeleteVideo(e, video)}
          title="動画を削除"
        >
          {#if deletingVideoId === video.id}
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
          <!-- サムネイル -->
          <div class="video-thumbnail-container">
            <div class="video-thumbnail">
              <img
                src={getThumbnailUrl(video.filename)}
                alt={video.filename}
                on:error={handleImageError}
              />
              <div class="thumbnail-overlay">
                <button
                  class="overlay-button play-button"
                  on:click={() => handlePlayVideo(video)}
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
                <button
                  class="overlay-button zoom-button"
                  on:click={() => handleZoomThumbnail(video)}
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

          <!-- メタデータと字幕のコンテナ -->
          <div class="metadata-container">
            <!-- 動画情報 (タイトルと説明) -->
            <div class="video-info">
              {#if video.title}
                <div class="info-item">
                  <span class="info-label">タイトル:</span>
                  <span class="info-value">{video.title}</span>
                </div>
              {/if}
              {#if video.description}
                <div class="info-item">
                  <span class="info-label">説明:</span>
                  <span class="info-value">{video.description}</span>
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
  isOpen={showAlertDialog}
  variant={alertVariant}
  message={alertMessage}
  on:close={() => (showAlertDialog = false)}
/>
<ConfirmDialog
  isOpen={showConfirmDialog}
  message={confirmMessage}
  confirmText="削除"
  on:confirm={confirmDelete}
  on:cancel={cancelDelete}
/>

<!-- モーダル -->
<VideoPlayerDialog
  bind:visible={showVideoPlayer}
  videoUrl={currentVideoUrl}
  videoTitle="動画再生"
/>

<ThumbnailZoomDialog
  bind:visible={showThumbnailZoom}
  imageUrl={currentThumbnailUrl}
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
    transition:
      transform 0.18s ease,
      box-shadow 0.25s ease;
  }

  .video-item:hover {
    transform: translateY(-2px);
    box-shadow:
      0 18px 40px rgba(var(--theme-rgb-black), 0.35),
      0 0 24px rgba(var(--theme-rgb-accent), 0.18);
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
    transform: scale(1.08);
    box-shadow: 0 10px 18px rgba(var(--theme-rgb-danger), 0.35);
    background: linear-gradient(
      145deg,
      rgba(var(--theme-rgb-danger), 0.92) 0%,
      rgba(var(--theme-rgb-red-dark), 0.85) 100%
    );
  }

  .delete-button:active {
    transform: scale(1.05);
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

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .video-content {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 1rem;
  }

  .metadata-container {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .video-thumbnail-container {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .video-thumbnail {
    position: relative;
    width: 160px;
    height: 90px;
    border-radius: 6px;
    overflow: hidden;
    background: rgba(var(--theme-rgb-black), 0.4);
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
    transform: scale(1.15);
    box-shadow: 0 4px 16px rgba(var(--theme-rgb-accent), 0.4);
  }

  .overlay-button:active {
    transform: scale(1.05);
  }

  /* 動画情報 (タイトル・説明) */
  .video-info {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.85rem;
    padding: 0.5rem;
    border-radius: 6px;
  }

  .info-item {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .info-label {
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 0.8rem;
    min-width: 60px;
    flex-shrink: 0;
  }

  .info-value {
    color: var(--accent-color);
    font-weight: 500;
    word-break: break-all;
    overflow-wrap: break-word;
    flex: 1;
  }

  .info-value-dim {
    color: rgba(var(--theme-rgb-orange-alt), 0.8);
    font-style: italic;
    font-size: 0.8rem;
  }

  /* 字幕情報 */
  .subtitle-info {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.85rem;
    padding: 0.5rem;
    border-radius: 6px;
  }

  .metadata-row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .metadata-item {
    display: flex;
    gap: 0.25rem;
    align-items: center;
  }

  .metadata-label {
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 0.8rem;
  }

  .metadata-value {
    color: var(--accent-color);
    font-weight: 500;
    word-break: break-all;
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
</style>
