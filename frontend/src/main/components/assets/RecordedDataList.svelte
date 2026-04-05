<script lang="ts">
  import { onMount } from 'svelte';
  import type { RecordedVideo } from '../../api/types';
  import type { EditableMetadata } from '../../metadata/editable';
  import { buildMetadataOptionMap, getMetadataOptions } from '../../api/metadata';
  import { normaliseWeaponSlots, toEditableMetadata } from '../../metadata/editable';
  import MetadataEditDialog from '../metadata/MetadataEditDialog.svelte';
  import VideoPlayerDialog from '../media/VideoPlayerDialog.svelte';
  import ThumbnailZoomDialog from '../media/ThumbnailZoomDialog.svelte';
  import SubtitleEditorDialog from '../metadata/SubtitleEditorDialog.svelte';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import ConfirmDialog from '../../../common/components/ConfirmDialog.svelte';

  interface Props {
    videos?: RecordedVideo[];
    onRefresh?: () => void;
    onModalOpen?: () => void;
    onModalClose?: () => void;
  }

  let { videos = $bindable([]), onRefresh, onModalOpen, onModalClose }: Props = $props();

  let editingVideo = $state<RecordedVideo | null>(null);
  let showMetadataDialog = $state(false);
  let showVideoPlayer = $state(false);
  let showThumbnailZoom = $state(false);
  let showSubtitleEditor = $state(false);
  let showAlertDialog = $state(false);
  let showConfirmDialog = $state(false);
  let alertMessage = $state('');
  let alertVariant = $state<'info' | 'success' | 'warning' | 'error'>('info');
  let confirmMessage = $state('');
  let pendingDeleteVideo = $state<RecordedVideo | null>(null);
  let currentVideoUrl = $state('');
  let currentThumbnailUrl = $state('');
  // $state ではなく普通の変数で保持することで、$effect の依存ループを避ける
  let wasModalOpen = false;
  let deletingVideoId = $state<string | null>(null); // 削除中の動画ID
  let metadataOptionMap = $state<ReturnType<typeof buildMetadataOptionMap> | null>(null);

  async function loadMetadataOptions(): Promise<void> {
    try {
      const options = await getMetadataOptions();
      metadataOptionMap = buildMetadataOptionMap(options);
    } catch (error) {
      console.error('Failed to load metadata options:', error);
    }
  }

  // モーダルの開閉状態を監視（$derived で計算し $effect で副作用を実行）
  const isAnyModalOpen = $derived(
    showMetadataDialog ||
      showVideoPlayer ||
      showThumbnailZoom ||
      showSubtitleEditor ||
      showAlertDialog ||
      showConfirmDialog
  );

  $effect(() => {
    // isAnyModalOpen は $derived（非 $state）なので、wasModalOpen への書き込みで再実行されない
    if (isAnyModalOpen && !wasModalOpen) {
      onModalOpen?.();
      wasModalOpen = true;
    } else if (!isAnyModalOpen && wasModalOpen) {
      onModalClose?.();
      wasModalOpen = false;
    }
  });

  function getThumbnailUrl(filename: string): string {
    // ファイル名から拡張子を除去して .png を追加
    const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
    return `/thumbnails/recorded/${encodeURIComponent(nameWithoutExt)}.png`;
  }

  function getVideoUrl(videoId: string): string {
    // videoIdはbase_dirからの相対パス（例: recorded/xxx.mkv）
    return `/videos/recorded/${encodeURIComponent(videoId)}`;
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

  function hasDetectedWeapon(value: string[] | null | undefined): boolean {
    return normaliseWeaponSlots(value, '不明').some(
      (weapon) => weapon.trim() !== '' && weapon !== '不明'
    );
  }

  function formatWeaponSlots(value: string[] | null | undefined): string {
    return normaliseWeaponSlots(value, '不明')
      .map((weapon) => weapon.trim() || '不明')
      .join('\n');
  }

  onMount(() => {
    void loadMetadataOptions();
  });

  function handlePlayVideo(video: RecordedVideo): void {
    currentVideoUrl = getVideoUrl(video.id);
    showVideoPlayer = true;
  }

  function handleZoomThumbnail(video: RecordedVideo): void {
    currentThumbnailUrl = getThumbnailUrl(video.filename);

    showThumbnailZoom = true;
  }

  function handleEditMetadata(video: RecordedVideo): void {
    editingVideo = video;
    showMetadataDialog = true;
  }

  function triggerActionOnKeydown(event: KeyboardEvent, action: () => void): void {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }

    event.preventDefault();
    action();
  }

  function handleEditSubtitle(event: MouseEvent, video: RecordedVideo): void {
    event.stopPropagation(); // メタデータダイアログが開かないようにする
    editingVideo = video;
    currentVideoUrl = getVideoUrl(video.path);
    showSubtitleEditor = true;
  }

  async function handleSaveMetadata(data: {
    videoId: string;
    metadata: EditableMetadata;
  }): Promise<void> {
    const { videoId, metadata } = data;
    console.log('Saving metadata for video:', videoId, metadata);

    try {
      const { updateRecordedVideoMetadata } = await import('../../api/metadata');
      const updatedVideo = await updateRecordedVideoMetadata(videoId, metadata);
      console.log('Metadata saved successfully:', updatedVideo);

      // ビデオリストを更新
      const index = videos.findIndex((v) => v.id === videoId);
      console.log('Found video at index:', index, 'out of', videos.length);

      if (index !== -1) {
        // Svelte 5 では $bindable プロップの要素ミューテーションを確実に検知させるため再代入する
        videos = videos.with(index, updatedVideo);
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
    onRefresh?.();
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
      onRefresh?.();
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

<div class="video-list glass-scroller" data-testid="recorded-video-list">
  {#if videos.length === 0}
    <div class="empty-state glass-panel">
      <div class="empty-icon">📁</div>
      <p>録画済データはありません</p>
    </div>
  {:else}
    {#each videos as video (video.id)}
      <div class="video-item glass-card" data-testid="recorded-video-item">
        <!-- 削除ボタン (フローティング右上) -->
        <button
          class="delete-button glass-icon-button"
          class:deleting={deletingVideoId === video.id}
          disabled={deletingVideoId === video.id}
          onclick={(e) => handleDeleteVideo(e, video)}
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
          <!-- メタデータと字幕のコンテナ -->
          <div class="metadata-container">
            <!-- サムネイル -->
            <div class="video-thumbnail-container">
              <div class="video-thumbnail">
                <img
                  src={getThumbnailUrl(video.filename)}
                  alt={video.filename}
                  onerror={handleImageError}
                />
                <div class="thumbnail-overlay">
                  <button
                    class="overlay-button play-button"
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
                  <button
                    class="overlay-button zoom-button"
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

            <!-- メタデータ (クリック可能) -->
            <div
              class="video-metadata"
              role="button"
              tabindex="0"
              data-testid="recorded-video-metadata-button"
              onclick={() => handleEditMetadata(video)}
              onkeydown={(event) => triggerActionOnKeydown(event, () => handleEditMetadata(video))}
            >
              <div class="metadata-main">
                <div class="metadata-row">
                  <div class="metadata-item">
                    <span class="metadata-label">開始時間:</span>
                    <span class="metadata-value" data-testid="recorded-video-started-at">
                      {formatTimestamp(video.startedAt)}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item" class:incomplete={!video.gameMode}>
                    <span class="metadata-label">モード:</span>
                    <span class="metadata-value" data-testid="recorded-video-game-mode">
                      {resolveMetadataLabel(
                        video.gameMode,
                        metadataOptionMap?.gameModes ?? null,
                        '未取得'
                      )}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item" class:incomplete={!video.match}>
                    <span class="metadata-label">マッチ:</span>
                    <span class="metadata-value" data-testid="recorded-video-match">
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
                    <span class="metadata-value" data-testid="recorded-video-rule">
                      {resolveMetadataLabel(video.rule, metadataOptionMap?.rules ?? null, '未取得')}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item" class:incomplete={!video.stage}>
                    <span class="metadata-label">ステージ:</span>
                    <span class="metadata-value" data-testid="recorded-video-stage">
                      {resolveMetadataLabel(
                        video.stage,
                        metadataOptionMap?.stages ?? null,
                        '未取得'
                      )}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item" class:incomplete={!video.rate}>
                    <span class="metadata-label">レート:</span>
                    <span class="metadata-value" data-testid="recorded-video-rate">
                      {video.rate ?? '未検出'}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item" class:incomplete={!video.judgement}>
                    <span class="metadata-label">判定:</span>
                    <span
                      class="metadata-value {getJudgementClass(video.judgement ?? '')}"
                      data-testid="recorded-video-judgement"
                    >
                      {resolveMetadataLabel(
                        video.judgement,
                        metadataOptionMap?.judgements ?? null,
                        '未判定'
                      )}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item stat-item">
                    <span class="metadata-label">キルレ:</span>
                    <span class="stat-icon">💀</span>
                    <span class="stat-value">
                      <span data-testid="recorded-video-kill">{video.kill ?? 0}</span>K/
                      <span data-testid="recorded-video-death">{video.death ?? 0}</span>D
                    </span>
                  </div>
                  <div class="metadata-item stat-item special-stat-item">
                    <span class="metadata-label metadata-label-placeholder" aria-hidden="true"
                    ></span>
                    <span class="stat-icon">✨</span>
                    <span class="stat-value">
                      SP×<span data-testid="recorded-video-special">{video.special ?? 0}</span>
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div class="metadata-item">
                    <span class="metadata-label">表彰:</span>
                    <span class="stat-value">
                      🥇x<span data-testid="recorded-video-gold-medals"
                        >{video.goldMedals ?? 0}</span
                      >
                      {' '}
                      🥈x<span data-testid="recorded-video-silver-medals">
                        {video.silverMedals ?? 0}
                      </span>
                    </span>
                  </div>
                </div>
              </div>
              <!-- /metadata-main -->
              <div class="metadata-weapons">
                <div class="metadata-row">
                  <div
                    class="metadata-item weapon-item"
                    class:incomplete={!hasDetectedWeapon(video.allies)}
                  >
                    <span class="metadata-label">味方ブキ:</span>
                    <span class="metadata-value weapon-value" data-testid="recorded-video-allies">
                      {formatWeaponSlots(video.allies)}
                    </span>
                  </div>
                </div>
                <div class="metadata-row">
                  <div
                    class="metadata-item weapon-item"
                    class:incomplete={!hasDetectedWeapon(video.enemies)}
                  >
                    <span class="metadata-label">敵ブキ:</span>
                    <span class="metadata-value weapon-value" data-testid="recorded-video-enemies">
                      {formatWeaponSlots(video.enemies)}
                    </span>
                  </div>
                </div>
              </div>
              <!-- /metadata-weapons -->
            </div>

            <!-- 字幕情報（独立した要素） -->
            <div
              class="subtitle-metadata"
              onclick={(e) => {
                e.stopPropagation();
                handleEditSubtitle(e, video);
              }}
              onkeydown={(event) =>
                triggerActionOnKeydown(event, () => {
                  editingVideo = video;
                  currentVideoUrl = getVideoUrl(video.path);
                  showSubtitleEditor = true;
                })}
              role="button"
              tabindex="0"
            >
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

<!-- モーダル -->
{#if editingVideo}
  <MetadataEditDialog
    bind:visible={showMetadataDialog}
    videoId={editingVideo.path}
    metadata={toEditableMetadata(editingVideo)}
    onSave={handleSaveMetadata}
  />

  <SubtitleEditorDialog
    bind:visible={showSubtitleEditor}
    videoId={editingVideo.path}
    videoUrl={currentVideoUrl}
    onSaved={handleSaveSubtitle}
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
  onClose={() => (showAlertDialog = false)}
/>

<!-- 確認ダイアログ -->
<ConfirmDialog
  isOpen={showConfirmDialog}
  message={confirmMessage}
  confirmText="削除"
  cancelText="キャンセル"
  onConfirm={confirmDelete}
  onCancel={cancelDelete}
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
    container-type: inline-size;
    transition: box-shadow 0.25s ease;
  }

  .video-item:hover {
    box-shadow:
      0 10px 22px rgba(var(--theme-rgb-black), 0.24),
      0 0 12px rgba(var(--theme-rgb-accent), 0.12);
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

  .video-metadata {
    --metadata-label-width: 4rem;
    display: block;
    font-size: 0.85rem;
    background: transparent;
    border: none;
    padding: 0 0.5rem 0.5rem;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
    outline: none;
  }

  .video-metadata:hover {
    background: rgba(var(--theme-rgb-accent), 0.08);
  }

  .video-metadata:focus-visible {
    box-shadow: 0 0 0 1px rgba(var(--theme-rgb-accent), 0.55);
    background: rgba(var(--theme-rgb-accent), 0.1);
  }

  /* 字幕メタデータ */
  .subtitle-metadata {
    --metadata-label-width: 4rem;
    display: block;
    font-size: 0.85rem;
    background: transparent;
    border: none;
    border-top: 1px solid rgba(var(--theme-rgb-white), 0.1);
    margin-top: 0.35rem;
    padding: 0.75rem 0.5rem 0.5rem;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
    outline: none;
  }

  .subtitle-metadata:hover {
    background: rgba(var(--theme-rgb-accent), 0.08);
  }

  .subtitle-metadata:focus-visible {
    box-shadow: 0 0 0 1px rgba(var(--theme-rgb-accent), 0.55);
    background: rgba(var(--theme-rgb-accent), 0.1);
  }

  .metadata-row {
    display: block;
    margin: 0 0 0.35rem;
  }

  .metadata-row:last-child {
    margin-bottom: 0;
  }

  .metadata-item {
    display: inline-flex;
    flex-wrap: nowrap;
    gap: 0.35rem;
    align-items: baseline;
    margin: 0 0.75rem 0.25rem 0;
    vertical-align: top;
    min-width: 0;
  }

  .weapon-item {
    display: flex;
    flex-wrap: nowrap;
    align-items: flex-start;
    width: 100%;
    margin-right: 0;
    gap: 0.35rem;
  }

  .weapon-item .metadata-label {
    flex: 0 0 var(--metadata-label-width);
  }

  .weapon-item .metadata-value {
    flex: 1 1 auto;
    min-width: 0;
    word-break: break-word;
  }

  .weapon-value {
    white-space: pre-wrap;
  }

  .metadata-label {
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 0.8rem;
    flex: 0 0 var(--metadata-label-width);
    width: var(--metadata-label-width);
  }

  .metadata-value {
    color: var(--accent-color);
    font-weight: 500;
    word-break: break-all;
    overflow-wrap: break-word;
    min-width: 0;
  }

  .metadata-label-placeholder {
    visibility: hidden;
  }

  .special-stat-item .metadata-label-placeholder {
    flex-basis: 0.5rem;
    width: 0.5rem;
  }

  .metadata-item.incomplete .metadata-value {
    color: rgba(var(--theme-rgb-orange-alt), 0.8);
    font-style: italic;
  }

  .judgement-win {
    color: var(--theme-status-success) !important;
    font-weight: 600;
  }

  .judgement-lose {
    color: var(--theme-status-danger) !important;
    font-weight: 600;
  }

  .stat-item {
    gap: 0.35rem;
  }

  .stat-icon {
    font-size: 0.9rem;
  }

  .stat-value {
    color: rgba(var(--theme-rgb-white), 0.9);
    font-weight: 500;
    font-size: 0.85rem;
    min-width: 0;
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

  @container (min-width: 750px) {
    .video-metadata {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0 1.5rem;
      align-items: start;
    }

    .metadata-main {
      grid-column: 1;
    }

    .metadata-weapons {
      grid-column: 2;
    }
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
