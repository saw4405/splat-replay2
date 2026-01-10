<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { RecordedVideo } from '../../api/types';
  import { buildMetadataOptionMap, getMetadataOptions } from '../../api/metadata';
  import MetadataEditDialog from '../metadata/MetadataEditDialog.svelte';
  import VideoPlayerDialog from '../media/VideoPlayerDialog.svelte';
  import ThumbnailZoomDialog from '../media/ThumbnailZoomDialog.svelte';
  import SubtitleEditorDialog from '../metadata/SubtitleEditorDialog.svelte';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import ConfirmDialog from '../../../common/components/ConfirmDialog.svelte';

  export let videos: RecordedVideo[] = [];

  const dispatch = createEventDispatcher();

  let editingVideo: RecordedVideo | null = null;
  let showMetadataDialog = false;
  let showVideoPlayer = false;
  let showThumbnailZoom = false;
  let showSubtitleEditor = false;
  let showAlertDialog = false;
  let showConfirmDialog = false;
  let alertMessage = '';
  let alertVariant: 'info' | 'success' | 'warning' | 'error' = 'info';
  let confirmMessage = '';
  let pendingDeleteVideo: RecordedVideo | null = null;
  let currentVideoUrl = '';
  let currentThumbnailUrl = '';
  let currentVideoTitle = '';
  let wasModalOpen = false; // モーダルが開いていたかどうかを追跡
  let deletingVideoId: string | null = null; // 削除中の動画ID
  let metadataOptionMap: ReturnType<typeof buildMetadataOptionMap> | null = null;

  async function loadMetadataOptions(): Promise<void> {
    try {
      const options = await getMetadataOptions();
      metadataOptionMap = buildMetadataOptionMap(options);
    } catch (error) {
      console.error('Failed to load metadata options:', error);
    }
  }

  // モーダルの開閉状態を監視
  $: {
    const isAnyModalOpen =
      showMetadataDialog ||
      showVideoPlayer ||
      showThumbnailZoom ||
      showSubtitleEditor ||
      showAlertDialog ||
      showConfirmDialog;

    if (isAnyModalOpen && !wasModalOpen) {
      // モーダルが開いた
      console.log('RecordedDataList: Modal opened, dispatching modalOpen');
      dispatch('modalOpen');
      wasModalOpen = true;
    } else if (!isAnyModalOpen && wasModalOpen) {
      // モーダルが閉じた
      console.log('RecordedDataList: Modal closed, dispatching modalClose');
      dispatch('modalClose');
      wasModalOpen = false;
    }
  }

  function getThumbnailUrl(filename: string): string {
    // ファイル名から拡張子を除去して .png を追加
    const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
    return `/api/thumbnails/recorded/${encodeURIComponent(nameWithoutExt)}.png`;
  }

  function getVideoUrl(videoId: string): string {
    // videoIdはフルパスなので、そのまま使用
    return `/api/videos/recorded/${encodeURIComponent(videoId)}`;
  }

  function handleImageError(e: Event): void {
    const img = e.currentTarget as HTMLImageElement;
    img.src =
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='90'%3E%3Crect fill='%23333' width='160' height='90'/%3E%3Ctext fill='%23666' x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='12'%3ENo Image%3C/text%3E%3C/svg%3E";
  }

  function formatTimestamp(timestamp: string | null): string {
    if (!timestamp) return '未開始';

    try {
      const date = new Date(timestamp);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
    } catch {
      return timestamp;
    }
  }

  function getJudgementClass(judgement: string): string {
    if (judgement === 'WIN') return 'judgement-win';
    if (judgement === 'LOSE') return 'judgement-lose';
    return '';
  }

  function resolveMetadataLabel(
    value: string | null,
    map: Record<string, string> | null,
    fallback: string
  ): string {
    if (!value) {
      return fallback;
    }
    if (!map) {
      return value;
    }
    return map[value] ?? value;
  }

  onMount(() => {
    void loadMetadataOptions();
  });

  function handlePlayVideo(video: RecordedVideo): void {
    currentVideoUrl = getVideoUrl(video.path); // フルパスを使用
    currentVideoTitle = video.filename;
    showVideoPlayer = true;
  }

  function handleZoomThumbnail(video: RecordedVideo): void {
    currentThumbnailUrl = getThumbnailUrl(video.filename);
    // サムネイルファイル名を設定
    const nameWithoutExt = video.filename.replace(/\.[^/.]+$/, '');
    currentVideoTitle = `${nameWithoutExt}.png`;
    showThumbnailZoom = true;
  }

  function handleEditMetadata(video: RecordedVideo): void {
    editingVideo = video;
    showMetadataDialog = true;
  }

  function handleEditSubtitle(event: MouseEvent, video: RecordedVideo): void {
    event.stopPropagation(); // メタデータダイアログが開かないようにする
    editingVideo = video;
    currentVideoUrl = getVideoUrl(video.path);
    currentVideoTitle = video.filename;
    showSubtitleEditor = true;
  }

  async function handleSaveMetadata(event: CustomEvent): Promise<void> {
    const { videoId, metadata } = event.detail;
    console.log('Saving metadata for video:', videoId, metadata);

    try {
      const { updateRecordedVideoMetadata } = await import('../../api/metadata');
      const updatedVideo = await updateRecordedVideoMetadata(videoId, metadata);
      console.log('Metadata saved successfully:', updatedVideo);

      // ビデオリストを更新
      const index = videos.findIndex((v) => v.id === videoId);
      console.log('Found video at index:', index, 'out of', videos.length);

      if (index !== -1) {
        videos[index] = updatedVideo;
        videos = [...videos]; // 新しい配列を作成してリアクティビティを確実にトリガー
        console.log('Video list updated');
      } else {
        console.warn('Video not found in list:', videoId);
      }

      showMetadataDialog = false;
      editingVideo = null;
    } catch (error) {
      console.error('Failed to save metadata:', error);
      alertMessage = `メタデータの保存に失敗しました: ${error}`;
      alertVariant = 'error';
      showAlertDialog = true;
    }
  }

  async function handleSaveSubtitle(): Promise<void> {
    console.log('Subtitle saved');
    // ビデオリストを再読み込みして hasSubtitles を更新
    dispatch('refresh');
    showSubtitleEditor = false;
    editingVideo = null;
  }

  async function handleDeleteVideo(event: MouseEvent, video: RecordedVideo): Promise<void> {
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
      const { deleteRecordedVideo } = await import('../../api/assets');
      await deleteRecordedVideo(video.path);
      console.log('Video deleted successfully:', video.path);

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
      <div class="empty-icon">📁</div>
      <p>録画済データはありません</p>
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
            <span class="video-timestamp">{formatTimestamp(video.startedAt)}</span>
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
            <!-- メタデータ (クリック可能) -->
            <button class="video-metadata" on:click={() => handleEditMetadata(video)}>
              <div class="metadata-row">
                <div class="metadata-item" class:incomplete={!video.match}>
                  <span class="metadata-label">マッチ:</span>
                  <span class="metadata-value">
                    {resolveMetadataLabel(
                      video.match,
                      metadataOptionMap?.matches ?? null,
                      '未取得'
                    )}
                  </span>
                </div>
              </div>
              <div class="metadata-row">
                <div class="metadata-item" class:incomplete={!video.rule}>
                  <span class="metadata-label">ルール:</span>
                  <span class="metadata-value">
                    {resolveMetadataLabel(video.rule, metadataOptionMap?.rules ?? null, '未取得')}
                  </span>
                </div>
              </div>
              <div class="metadata-row">
                <div class="metadata-item" class:incomplete={!video.stage}>
                  <span class="metadata-label">ステージ:</span>
                  <span class="metadata-value">
                    {resolveMetadataLabel(video.stage, metadataOptionMap?.stages ?? null, '未取得')}
                  </span>
                </div>
              </div>
              <div class="metadata-row">
                <div class="metadata-item" class:incomplete={!video.rate}>
                  <span class="metadata-label">レート:</span>
                  <span class="metadata-value">{video.rate ?? '未検出'}</span>
                </div>
              </div>
              <div class="metadata-row">
                <div class="metadata-item" class:incomplete={!video.judgement}>
                  <span class="metadata-label">判定:</span>
                  <span class="metadata-value {getJudgementClass(video.judgement ?? '')}">
                    {resolveMetadataLabel(
                      video.judgement,
                      metadataOptionMap?.judgements ?? null,
                      '未判定'
                    )}
                  </span>
                </div>
                <div class="metadata-item stat-item">
                  <span class="stat-icon">💀</span>
                  <span class="stat-value">{video.kill ?? 0}K/{video.death ?? 0}D</span>
                </div>
                <div class="metadata-item stat-item">
                  <span class="stat-icon">✨</span>
                  <span class="stat-value">SP×{video.special ?? 0}</span>
                </div>
              </div>
            </button>

            <div class="metadata-row stats-row"></div>

            <!-- 字幕情報（独立した要素） -->
            <button
              class="subtitle-metadata"
              on:click={(e) => {
                e.stopPropagation();
                handleEditSubtitle(e, video);
              }}
            >
              <div class="metadata-row">
                <div class="metadata-item subtitle-item">
                  <span class="metadata-label">字幕:</span>
                  <span class="metadata-value" class:has-subtitles={video.hasSubtitles}>
                    {video.hasSubtitles ? '✓ あり' : '✗ なし'}
                  </span>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>
    {/each}
  {/if}
</div>

<!-- モーダル -->
{#if editingVideo}
  <MetadataEditDialog
    bind:visible={showMetadataDialog}
    videoId={editingVideo.path}
    metadata={{
      match: editingVideo.match ?? '',
      rule: editingVideo.rule ?? '',
      stage: editingVideo.stage ?? '',
      rate: editingVideo.rate ?? '',
      judgement: editingVideo.judgement ?? '',
      kill: editingVideo.kill ?? 0,
      death: editingVideo.death ?? 0,
      special: editingVideo.special ?? 0,
    }}
    on:save={handleSaveMetadata}
  />

  <SubtitleEditorDialog
    bind:visible={showSubtitleEditor}
    videoId={editingVideo.path}
    videoUrl={currentVideoUrl}
    videoTitle={currentVideoTitle}
    on:saved={handleSaveSubtitle}
  />
{/if}

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

<!-- アラートダイアログ -->
<NotificationDialog
  isOpen={showAlertDialog}
  variant={alertVariant}
  message={alertMessage}
  on:close={() => (showAlertDialog = false)}
/>

<!-- 確認ダイアログ -->
<ConfirmDialog
  isOpen={showConfirmDialog}
  message={confirmMessage}
  confirmText="削除"
  cancelText="キャンセル"
  on:confirm={confirmDelete}
  on:cancel={cancelDelete}
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
    flex: 0 0 auto;
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.25rem;
    width: 100%;
    box-sizing: border-box;
    transition:
      transform 0.18s ease,
      box-shadow 0.25s ease;
  }

  .video-item:hover {
    transform: translateY(-2px);
    box-shadow:
      0 18px 40px rgba(0, 0, 0, 0.35),
      0 0 24px rgba(25, 211, 199, 0.18);
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
    color: rgba(255, 255, 255, 0.72);
    padding: 0;
    transition: all 0.2s ease;
    opacity: 0;
    z-index: 10;
  }

  .video-item:hover .delete-button {
    opacity: 1;
  }

  .delete-button:hover {
    color: #fff;
    transform: scale(1.08);
    box-shadow: 0 10px 18px rgba(244, 67, 54, 0.35);
    background: linear-gradient(145deg, rgba(244, 67, 54, 0.92) 0%, rgba(190, 40, 28, 0.85) 100%);
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
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff;
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

  .video-timestamp {
    font-size: 0.85rem;
    font-weight: 600;
    color: #19d3c7;
    word-break: break-all;
    overflow-wrap: break-word;
  }

  .video-thumbnail {
    position: relative;
    width: 160px;
    height: 90px;
    border-radius: 6px;
    overflow: hidden;
    background: rgba(0, 0, 0, 0.4);
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
    background: rgba(0, 0, 0, 0.5);
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
    background: rgba(0, 0, 0, 0.6);
    border: 2px solid rgba(255, 255, 255, 0.8);
    border-radius: 50%;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
    color: #fff;
    padding: 0;
  }

  .overlay-button svg {
    width: 20px;
    height: 20px;
  }

  .overlay-button:hover {
    background: rgba(25, 211, 199, 0.9);
    border-color: #19d3c7;
    transform: scale(1.15);
    box-shadow: 0 4px 16px rgba(25, 211, 199, 0.4);
  }

  .overlay-button:active {
    transform: scale(1.05);
  }

  .video-metadata {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.85rem;
    background: transparent;
    border: none;
    padding: 0.5rem;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
    width: 100%;
  }

  .video-metadata:hover {
    background: rgba(25, 211, 199, 0.08);
  }

  /* 字幕メタデータ */
  .subtitle-metadata {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.85rem;
    background: transparent;
    border: none;
    padding: 0.5rem;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
    width: 100%;
  }

  .subtitle-metadata:hover {
    background: rgba(25, 211, 199, 0.08);
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
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.8rem;
  }

  .metadata-value {
    color: #19d3c7;
    font-weight: 500;
    word-break: break-all;
    overflow-wrap: break-word;
  }

  .metadata-item.incomplete .metadata-value {
    color: rgba(255, 165, 0, 0.8);
    font-style: italic;
  }

  .judgement-win {
    color: #4caf50 !important;
    font-weight: 600;
  }

  .judgement-lose {
    color: #f44336 !important;
    font-weight: 600;
  }

  .stats-row {
    padding-top: 0.25rem;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .stat-item {
    gap: 0.35rem;
  }

  .stat-icon {
    font-size: 0.9rem;
  }

  .stat-value {
    color: rgba(255, 255, 255, 0.9);
    font-weight: 500;
    font-size: 0.85rem;
  }

  /* 字幕情報アイテム */
  .subtitle-item .metadata-value.has-subtitles {
    color: #4caf50;
  }

  .subtitle-item .metadata-value:not(.has-subtitles) {
    color: rgba(255, 165, 0, 0.8);
  }

  /* スクロールバースタイル */
  .video-list::-webkit-scrollbar {
    width: 6px;
  }

  .video-list::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
  }

  .video-list::-webkit-scrollbar-thumb {
    background: rgba(25, 211, 199, 0.3);
    border-radius: 3px;
  }

  .video-list::-webkit-scrollbar-thumb:hover {
    background: rgba(25, 211, 199, 0.5);
  }

  @media (max-width: 1024px) {
    .video-list {
      min-height: clamp(3rem, 20vh, 6rem);
    }
  }
</style>
