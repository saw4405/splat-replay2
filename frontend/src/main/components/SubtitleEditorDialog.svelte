<script lang="ts">
  import { onMount } from 'svelte';
  import BaseDialog from './BaseDialog.svelte';
  import type { SubtitleBlock, SubtitleData } from './../api';
  import { getRecordedSubtitle, updateRecordedSubtitle } from './../api';

  export let visible = false;
  export let videoId: string;
  export let videoUrl: string;
  // 外部参照用（現在は未使用だが、将来的にタイトル表示などで使用予定）
  export const videoTitle: string = '';

  let subtitleData: SubtitleData | null = null;
  let blocks: SubtitleBlock[] = [];
  let videoDuration: number | null = null;
  let loading = true;
  let saving = false;
  let error: string | null = null;

  // 動画プレイヤー
  let videoElement: HTMLVideoElement;
  let currentTime = 0;
  let playing = false;
  let selectedBlockIndex: number | null = null;

  // タイムラインの状態
  let timelineWidth = 800; // デフォルト幅
  let timelineContainer: HTMLElement;
  let draggingBlock: number | null = null;
  let draggingEdge: 'start' | 'end' | 'move' | null = null;
  let dragStartX = 0;
  let dragStartTime = 0;

  // ポップアップ編集フォームの位置
  let popupLeft = 0;
  let popupTop = 0;
  let popupArrowLeft = 50; // 三角形の位置（%）
  let showPopup = false;

  // 字幕追加用のポップアップ
  let showAddPopup = false;
  let addPopupTime = 0;
  let addPopupLeft = 0;

  // フォーム入力時の重複チェック
  let editedStartTime = 0;
  let editedEndTime = 0;
  $: hasTimeOverlap =
    selectedBlockIndex !== null && hasOverlap(editedStartTime, editedEndTime, selectedBlockIndex);

  $: if (visible && videoId) {
    loadSubtitle();
  }

  $: if (!visible) {
    cleanup();
  }

  async function loadSubtitle() {
    loading = true;
    error = null;
    try {
      subtitleData = await getRecordedSubtitle(videoId);
      blocks = [...subtitleData.blocks];
      videoDuration = subtitleData.video_duration;
    } catch (err) {
      error = `字幕の読み込みに失敗しました: ${err}`;
      console.error(err);
    } finally {
      loading = false;
    }
  }

  async function saveSubtitle() {
    if (!subtitleData) return;

    saving = true;
    error = null;
    try {
      const updatedData: SubtitleData = {
        blocks: blocks.map((block, idx) => ({
          ...block,
          index: idx + 1,
        })),
        video_duration: videoDuration,
      };

      await updateRecordedSubtitle(videoId, updatedData);
      dispatchEvent(new CustomEvent('saved'));
      close();
    } catch (err) {
      error = `字幕の保存に失敗しました: ${err}`;
      console.error(err);
    } finally {
      saving = false;
    }
  }

  function close() {
    visible = false;
    cleanup();
  }

  function cleanup() {
    if (videoElement) {
      videoElement.pause();
      videoElement.currentTime = 0;
    }
    playing = false;
    selectedBlockIndex = null;
    draggingBlock = null;
  }

  function handleVideoTimeUpdate() {
    if (videoElement) {
      currentTime = videoElement.currentTime;
    }
  }

  function handleVideoPlay() {
    playing = true;
  }

  function handleVideoPause() {
    playing = false;
  }

  function _togglePlay() {
    if (!videoElement) return;
    if (playing) {
      videoElement.pause();
    } else {
      void videoElement.play();
    }
  }

  function seekToTime(time: number) {
    if (!videoElement) return;
    videoElement.currentTime = Math.max(0, Math.min(time, videoDuration || 0));
  }

  // 現在時刻に表示されている字幕を取得
  function getCurrentSubtitle(): string {
    const block = blocks.find((b) => currentTime >= b.start_time && currentTime <= b.end_time);
    return block ? block.text : '';
  }

  // currentTimeまたはblocksが変更されたら再計算
  $: currentSubtitleText = blocks && currentTime >= 0 ? getCurrentSubtitle() : '';

  // 時間重複チェック関数
  function hasOverlap(startTime: number, endTime: number, excludeIndex: number = -1): boolean {
    return blocks.some((block, idx) => {
      if (idx === excludeIndex) return false;
      // 重複判定: (start1 < end2) && (start2 < end1)
      return startTime < block.end_time && block.start_time < endTime;
    });
  }

  // 指定時間に既に字幕があるかチェック
  function hasSubtitleAt(time: number): boolean {
    return blocks.some((block) => time >= block.start_time && time < block.end_time);
  }

  function formatTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);

    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
    }
    return `${m}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
  }

  // mm:ss.000 形式から秒数に変換
  function parseTimeString(timeStr: string): number | null {
    // mm:ss.SSS または m:ss.SSS 形式をパース
    const match = timeStr.match(/^(\d{1,2}):(\d{2})\.(\d{3})$/);
    if (!match) return null;

    const minutes = parseInt(match[1], 10);
    const seconds = parseInt(match[2], 10);
    const milliseconds = parseInt(match[3], 10);

    if (seconds >= 60) return null;

    return minutes * 60 + seconds + milliseconds / 1000;
  }

  // 秒数を mm:ss.000 形式に変換（編集用）
  function formatTimeForEdit(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${m}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
  }

  function timeToPixel(time: number): number {
    if (!videoDuration || videoDuration === 0) return 0;
    return (time / videoDuration) * timelineWidth;
  }

  function pixelToTime(pixel: number): number {
    if (!videoDuration || videoDuration === 0) return 0;
    return (pixel / timelineWidth) * videoDuration;
  }

  function _addBlock() {
    const newStartTime = currentTime;
    const newEndTime = Math.min(currentTime + 2.5, videoDuration || currentTime + 2.5);

    const newBlock: SubtitleBlock = {
      index: blocks.length + 1,
      start_time: newStartTime,
      end_time: newEndTime,
      text: '新しい字幕',
    };

    blocks = [...blocks, newBlock].sort((a, b) => a.start_time - b.start_time);
    selectedBlockIndex = blocks.findIndex((b) => b === newBlock);
  }

  function deleteBlock(index: number) {
    if (confirm('この字幕ブロックを削除しますか?')) {
      blocks = blocks.filter((_, i) => i !== index);
      if (selectedBlockIndex === index) {
        selectedBlockIndex = null;
      }
    }
  }

  function selectBlock(index: number, event?: MouseEvent) {
    selectedBlockIndex = index;
    seekToTime(blocks[index].start_time);

    // 編集中の時間を初期化
    editedStartTime = blocks[index].start_time;
    editedEndTime = blocks[index].end_time;

    // ポップアップの位置を計算
    if (event && timelineContainer) {
      const _containerRect = timelineContainer.getBoundingClientRect();
      const blockLeft = timeToPixel(blocks[index].start_time);
      const blockWidth = timeToPixel(blocks[index].end_time - blocks[index].start_time);

      // ポップアップの幅を推定（実際の幅 = 300px + パディング）
      const popupWidth = 320;
      const halfPopupWidth = popupWidth / 2;

      // ブロックの中央を初期位置とする
      const blockCenter = blockLeft + blockWidth / 2;

      // エッジから安全な余白を考慮して範囲を設定
      const minLeft = halfPopupWidth + 10; // 左端から最小10pxの余白
      const maxLeft = timelineWidth - halfPopupWidth - 10; // 右端から最小10pxの余白

      // クリッピング防止: ブロック中心を基準にしつつ、安全範囲内に収める
      const calculatedLeft = Math.max(minLeft, Math.min(maxLeft, blockCenter));

      popupLeft = calculatedLeft;

      // 三角形の位置を計算（ポップアップ内での相対位置 %）
      // ブロック中央からポップアップ左端までの距離をパーセンテージで計算
      const arrowOffsetPx = blockCenter - calculatedLeft; // 負なら左、正なら右
      popupArrowLeft = 50 + (arrowOffsetPx / popupWidth) * 100;

      // 三角形が端に寄りすぎないように制限（10% ~ 90%）
      popupArrowLeft = Math.max(10, Math.min(90, popupArrowLeft));

      // タイムラインの上部に表示（タイムライン領域の上）
      popupTop = -20; // タイムラインコンテナからの相対位置（上方向）

      showPopup = true;
    }
  }

  // タイムラインのドラッグ操作
  function handleTimelineMouseDown(
    event: MouseEvent,
    blockIndex: number,
    edge: 'start' | 'end' | 'move'
  ) {
    event.preventDefault();
    event.stopPropagation();

    // 追加ポップアップを閉じる
    showAddPopup = false;

    draggingBlock = blockIndex;
    draggingEdge = edge;
    dragStartX = event.clientX;

    if (edge === 'move') {
      dragStartTime = blocks[blockIndex].start_time;
    } else if (edge === 'start') {
      dragStartTime = blocks[blockIndex].start_time;
    } else {
      dragStartTime = blocks[blockIndex].end_time;
    }

    window.addEventListener('mousemove', handleTimelineMouseMove);
    window.addEventListener('mouseup', handleTimelineMouseUp);
  }

  function handleTimelineMouseMove(event: MouseEvent) {
    if (draggingBlock === null || draggingEdge === null) return;

    const deltaX = event.clientX - dragStartX;
    const deltaTime = pixelToTime(deltaX);

    const block = blocks[draggingBlock];
    const duration = block.end_time - block.start_time;

    if (draggingEdge === 'start') {
      let newStart = Math.max(0, dragStartTime + deltaTime);
      const newEnd = Math.max(newStart + 0.5, block.end_time);

      // 他の字幕と重複しないかチェック
      if (!hasOverlap(newStart, newEnd, draggingBlock)) {
        blocks[draggingBlock] = {
          ...block,
          start_time: newStart,
          end_time: newEnd,
        };
      }
    } else if (draggingEdge === 'end') {
      let newEnd = Math.min(videoDuration || dragStartTime + deltaTime, dragStartTime + deltaTime);
      const newStart = Math.min(block.start_time, newEnd - 0.5);

      // 他の字幕と重複しないかチェック
      if (!hasOverlap(newStart, newEnd, draggingBlock)) {
        blocks[draggingBlock] = {
          ...block,
          start_time: newStart,
          end_time: newEnd,
        };
      }
    } else if (draggingEdge === 'move') {
      let newStart = dragStartTime + deltaTime;
      newStart = Math.max(0, Math.min(newStart, (videoDuration || 0) - duration));
      const newEnd = newStart + duration;

      // 他の字幕と重複しないかチェック
      if (!hasOverlap(newStart, newEnd, draggingBlock)) {
        blocks[draggingBlock] = {
          ...block,
          start_time: newStart,
          end_time: newEnd,
        };
      }
    }

    blocks = [...blocks];
  }

  function handleTimelineMouseUp() {
    draggingBlock = null;
    draggingEdge = null;
    window.removeEventListener('mousemove', handleTimelineMouseMove);
    window.removeEventListener('mouseup', handleTimelineMouseUp);
  }

  function handleTimelineClick(event: MouseEvent) {
    if (draggingBlock !== null) return; // ドラッグ中はクリック無視

    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = event.clientX - rect.left;
    const time = pixelToTime(x);
    seekToTime(time);

    // タイムライン背景をクリックしたら編集ポップアップを閉じる
    showPopup = false;
    selectedBlockIndex = null;

    // 既に字幕がある場合は追加ポップアップを表示しない
    if (hasSubtitleAt(time)) {
      showAddPopup = false;
      return;
    }

    // 追加ポップアップを表示
    addPopupTime = time;
    addPopupLeft = x;
    showAddPopup = true;
  }

  function handleAddPopupClick(event: MouseEvent | KeyboardEvent) {
    event.stopPropagation();
    const time = addPopupTime;
    const _clickX = addPopupLeft;
    showAddPopup = false;

    // 新しい字幕ブロックを追加
    const newBlock: SubtitleBlock = {
      index: blocks.length + 1,
      start_time: time,
      end_time: Math.min(time + 3, videoDuration || time + 3),
      text: '',
    };
    blocks = [...blocks, newBlock].sort((a, b) => a.start_time - b.start_time);
    blocks = blocks.map((b, i) => ({ ...b, index: i + 1 }));

    // 追加したブロックを選択して編集ポップアップを表示
    const addedIndex = blocks.findIndex((b) => b.start_time === time);
    if (addedIndex !== -1 && timelineContainer) {
      selectedBlockIndex = addedIndex;
      editedStartTime = blocks[addedIndex].start_time;
      editedEndTime = blocks[addedIndex].end_time;

      // ポップアップの位置を計算
      const blockLeft = timeToPixel(blocks[addedIndex].start_time);
      const blockWidth = timeToPixel(blocks[addedIndex].end_time - blocks[addedIndex].start_time);

      const popupWidth = 320;
      const halfPopupWidth = popupWidth / 2;
      const blockCenter = blockLeft + blockWidth / 2;

      const minLeft = halfPopupWidth + 10;
      const maxLeft = timelineWidth - halfPopupWidth - 10;
      const calculatedLeft = Math.max(minLeft, Math.min(maxLeft, blockCenter));

      popupLeft = calculatedLeft;

      const arrowOffsetPx = blockCenter - calculatedLeft;
      popupArrowLeft = 50 + (arrowOffsetPx / popupWidth) * 100;
      popupArrowLeft = Math.max(10, Math.min(90, popupArrowLeft));

      popupTop = -20;
      showPopup = true;

      // 動画を追加した字幕の開始位置にシーク
      seekToTime(blocks[addedIndex].start_time);
    }
  }

  function closePopup() {
    showPopup = false;
    selectedBlockIndex = null;
  }

  onMount(() => {
    return () => {
      window.removeEventListener('mousemove', handleTimelineMouseMove);
      window.removeEventListener('mouseup', handleTimelineMouseUp);
    };
  });
</script>

{#if visible}
  <BaseDialog
    bind:open={visible}
    title="字幕編集"
    footerVariant="simple"
    primaryButtonText={saving ? '保存中...' : '保存'}
    secondaryButtonText="キャンセル"
    on:primary-click={saveSubtitle}
    on:secondary-click={close}
    disablePrimaryButton={saving || loading}
    disableSecondaryButton={saving}
    maxWidth="90vw"
    maxHeight="95vh"
  >
    {#if loading}
      <div class="loading">読み込み中...</div>
    {:else if error}
      <div class="error">{error}</div>
    {:else}
      <div class="dialog-body">
        <!-- 動画プレビュー -->
        <div class="video-preview">
          <div class="video-wrapper">
            <video
              bind:this={videoElement}
              src={videoUrl}
              on:timeupdate={handleVideoTimeUpdate}
              on:play={handleVideoPlay}
              on:pause={handleVideoPause}
              controls
            >
              <track kind="captions" />
            </video>
            <!-- 字幕プレビュー -->
            {#if currentSubtitleText}
              <div class="subtitle-overlay">
                {currentSubtitleText}
              </div>
            {/if}
          </div>
        </div>

        <!-- タイムライン -->
        <div class="timeline-section">
          <div
            class="timeline-container"
            bind:this={timelineContainer}
            bind:clientWidth={timelineWidth}
            on:click={handleTimelineClick}
            on:keydown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const rect = e.currentTarget.getBoundingClientRect();
                const clickEvent = new MouseEvent('click', {
                  clientX: rect.left + rect.width / 2,
                  clientY: rect.top + rect.height / 2,
                  bubbles: true,
                });
                e.currentTarget.dispatchEvent(clickEvent);
              }
            }}
            role="button"
            tabindex="0"
          >
            <!-- 時間軸 -->
            <div class="timeline-axis">
              {#if videoDuration}
                <!-- 30秒間隔でメモリを表示 -->
                {#each Array(Math.floor(videoDuration / 30) + 1) as _, i}
                  {@const time = i * 30}
                  {@const left = (time / videoDuration) * 100}
                  {#if time <= videoDuration}
                    <div class="timeline-tick" style="left: {left}%">
                      <div class="tick-line"></div>
                      <div class="tick-label">{formatTime(time)}</div>
                    </div>
                  {/if}
                {/each}
              {/if}
            </div>

            <!-- 現在位置インジケーター -->
            <div class="playhead" style="left: {timeToPixel(currentTime)}px"></div>

            <!-- 字幕ブロック -->
            <div class="timeline-blocks">
              {#each blocks as block, i}
                {@const left = timeToPixel(block.start_time)}
                {@const width = timeToPixel(block.end_time - block.start_time)}
                <div
                  class="subtitle-block"
                  class:selected={selectedBlockIndex === i}
                  style="left: {left}px; width: {width}px"
                  on:click|stopPropagation={(e) => selectBlock(i, e)}
                  on:keydown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      e.stopPropagation();
                      selectBlock(i);
                    }
                  }}
                  role="button"
                  tabindex="0"
                >
                  <!-- 左端ハンドル（開始時間調整） -->
                  <div
                    class="resize-handle left"
                    on:mousedown={(e) => handleTimelineMouseDown(e, i, 'start')}
                    role="button"
                    tabindex="-1"
                    aria-label="開始時間調整"
                  ></div>

                  <!-- 本体（移動） -->
                  <div
                    class="block-body"
                    on:mousedown={(e) => handleTimelineMouseDown(e, i, 'move')}
                    role="button"
                    tabindex="-1"
                    aria-label="字幕ブロック移動"
                  >
                    <div class="block-label">#{i + 1}</div>
                    <div class="block-text">{block.text}</div>
                  </div>

                  <!-- 右端ハンドル（終了時間調整） -->
                  <div
                    class="resize-handle right"
                    on:mousedown={(e) => handleTimelineMouseDown(e, i, 'end')}
                    role="button"
                    tabindex="-1"
                    aria-label="終了時間調整"
                  ></div>
                </div>
              {/each}
            </div>

            <!-- ポップアップ編集フォーム -->
            {#if showPopup && selectedBlockIndex !== null && blocks[selectedBlockIndex]}
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
              <div
                class="popup-editor"
                style="left: {popupLeft}px; top: {popupTop}px; --arrow-left: {popupArrowLeft}%"
                on:click|stopPropagation
                on:keydown={(e) => e.stopPropagation()}
                role="dialog"
                aria-label="字幕編集"
              >
                <div class="popup-header">
                  <span class="popup-title">字幕 #{selectedBlockIndex + 1}</span>
                  <button class="popup-close" on:click={closePopup}>✕</button>
                </div>
                <div class="popup-body">
                  <div class="popup-row">
                    <label>
                      開始
                      <input
                        type="text"
                        placeholder="0:00.000"
                        value={formatTimeForEdit(blocks[selectedBlockIndex].start_time)}
                        class:error={hasTimeOverlap}
                        on:input={(e) => {
                          const parsed = parseTimeString(e.currentTarget.value);
                          if (parsed !== null && selectedBlockIndex !== null) {
                            editedStartTime = parsed;
                            if (!hasOverlap(parsed, editedEndTime, selectedBlockIndex)) {
                              blocks[selectedBlockIndex].start_time = parsed;
                              blocks = [...blocks];
                            }
                          }
                        }}
                        on:blur={(e) => {
                          // フォーカスを失ったときに正しい形式に整形
                          if (selectedBlockIndex !== null) {
                            e.currentTarget.value = formatTimeForEdit(
                              blocks[selectedBlockIndex].start_time
                            );
                          }
                        }}
                      />
                    </label>
                    <label>
                      終了
                      <input
                        type="text"
                        placeholder="0:00.000"
                        value={formatTimeForEdit(blocks[selectedBlockIndex].end_time)}
                        class:error={hasTimeOverlap}
                        on:input={(e) => {
                          const parsed = parseTimeString(e.currentTarget.value);
                          if (parsed !== null && selectedBlockIndex !== null) {
                            editedEndTime = parsed;
                            if (!hasOverlap(editedStartTime, parsed, selectedBlockIndex)) {
                              blocks[selectedBlockIndex].end_time = parsed;
                              blocks = [...blocks];
                            }
                          }
                        }}
                        on:blur={(e) => {
                          // フォーカスを失ったときに正しい形式に整形
                          if (selectedBlockIndex !== null) {
                            e.currentTarget.value = formatTimeForEdit(
                              blocks[selectedBlockIndex].end_time
                            );
                          }
                        }}
                      />
                    </label>
                  </div>
                  {#if hasTimeOverlap}
                    <div class="overlap-warning">⚠️ 他の字幕と時間が重複しています</div>
                  {/if}
                  <div class="popup-row">
                    <label class="full-width">
                      テキスト
                      <textarea
                        value={blocks[selectedBlockIndex].text}
                        on:input={(e) => {
                          if (selectedBlockIndex !== null) {
                            blocks[selectedBlockIndex].text = e.currentTarget.value;
                            blocks = [...blocks];
                          }
                        }}
                        rows="2"
                      ></textarea>
                    </label>
                  </div>
                  <div class="popup-actions">
                    <button
                      class="delete-button"
                      on:click={() =>
                        selectedBlockIndex !== null && deleteBlock(selectedBlockIndex)}
                    >
                      🗑️ 削除
                    </button>
                  </div>
                </div>
              </div>
            {/if}

            <!-- 追加用の丸いポップアップ -->
            {#if showAddPopup}
              <div
                class="add-popup"
                style="left: {addPopupLeft}px;"
                on:click={handleAddPopupClick}
                on:keydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleAddPopupClick(e);
                  }
                }}
                role="button"
                tabindex="0"
                aria-label="字幕を追加"
              >
                <span class="add-icon">＋</span>
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/if}
  </BaseDialog>
{/if}

<style>
  .dialog-body {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  .loading,
  .error {
    padding: 40px;
    text-align: center;
    color: rgba(255, 255, 255, 0.7);
  }

  .error {
    color: #ff6b6b;
  }

  /* 動画プレビュー */
  .video-preview {
    margin-bottom: 24px;
  }

  .video-wrapper {
    position: relative;
    width: 100%;
  }

  .video-preview video {
    width: 100%;
    max-height: 400px;
    background: #000;
    border-radius: 4px;
    display: block;
  }

  .subtitle-overlay {
    position: absolute;
    bottom: 40px; /* 下部に近い位置に表示 */
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 16px;
    font-weight: bold;
    text-align: center;
    max-width: 80%;
    word-wrap: break-word;
    text-shadow:
      -2px -2px 0 #000,
      2px -2px 0 #000,
      -2px 2px 0 #000,
      2px 2px 0 #000,
      -2px 0 0 #000,
      2px 0 0 #000,
      0 -2px 0 #000,
      0 2px 0 #000;
    pointer-events: none;
    z-index: 10;
  }

  /* タイムライン */
  .timeline-section {
    margin-bottom: 24px;
  }

  .timeline-container {
    position: relative;
    height: 120px;
    background: rgba(42, 42, 42, 0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    cursor: crosshair;
    overflow: visible;
  }

  .timeline-axis {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 30px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .timeline-tick {
    position: absolute;
    top: 0;
    transform: translateX(-50%);
  }

  .tick-line {
    width: 1px;
    height: 8px;
    background: rgba(255, 255, 255, 0.3);
    margin: 0 auto;
  }

  .tick-label {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.5);
    margin-top: 2px;
    white-space: nowrap;
  }

  .playhead {
    position: absolute;
    top: 30px;
    bottom: 0;
    width: 2px;
    background: #ff4444;
    pointer-events: none;
    z-index: 10;
  }

  .playhead::before {
    content: '';
    position: absolute;
    top: -6px;
    left: -4px;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #ff4444;
  }

  .timeline-blocks {
    position: absolute;
    top: 35px;
    left: 0;
    right: 0;
    bottom: 5px;
  }

  .subtitle-block {
    position: absolute;
    height: 60px;
    background: rgba(76, 175, 255, 0.5);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 2px solid rgba(76, 175, 255, 0.8);
    border-radius: 8px;
    cursor: move;
    display: flex;
    align-items: center;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }

  .subtitle-block:hover {
    background: rgba(76, 175, 255, 0.7);
    border-color: rgba(76, 175, 255, 1);
    box-shadow: 0 4px 12px rgba(76, 175, 255, 0.3);
  }

  .subtitle-block.selected {
    background: rgba(255, 193, 7, 0.5);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-color: rgba(255, 193, 7, 1);
    box-shadow:
      0 4px 16px rgba(255, 193, 7, 0.4),
      0 0 0 1px rgba(255, 193, 7, 0.3);
  }

  .resize-handle {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 8px;
    cursor: ew-resize;
    background: rgba(255, 255, 255, 0.25);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    transition: all 0.2s;
  }

  .resize-handle:hover {
    background: rgba(255, 255, 255, 0.5);
  }

  .resize-handle.left {
    left: 0;
    border-radius: 6px 0 0 6px;
  }

  .resize-handle.right {
    right: 0;
    border-radius: 0 6px 6px 0;
  }

  .block-body {
    flex: 1;
    padding: 4px 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .block-label {
    font-size: 10px;
    font-weight: bold;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 2px;
  }

  .block-text {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.95);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ポップアップ編集フォーム */
  .popup-editor {
    position: absolute;
    background: rgba(30, 30, 30, 0.95);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 2px solid rgba(255, 193, 7, 0.8);
    border-radius: 12px;
    box-shadow:
      0 12px 32px rgba(0, 0, 0, 0.7),
      0 0 0 1px rgba(255, 193, 7, 0.2);
    z-index: 100;
    min-width: 300px;
    transform: translate(-50%, -100%);
    margin-top: -10px;
  }

  .popup-editor::after {
    content: '';
    position: absolute;
    bottom: -10px;
    left: var(--arrow-left, 50%);
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 10px solid transparent;
    border-right: 10px solid transparent;
    border-top: 10px solid rgba(255, 193, 7, 1);
  }

  .popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 193, 7, 0.15);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }

  .popup-title {
    font-size: 13px;
    font-weight: bold;
    color: rgba(255, 193, 7, 1);
  }

  .popup-close {
    background: none;
    border: none;
    color: rgba(255, 255, 255, 0.7);
    font-size: 18px;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.2s;
  }

  .popup-close:hover {
    background: rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 1);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }

  .popup-body {
    padding: 12px;
  }

  .popup-row {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }

  .popup-row:last-child {
    margin-bottom: 0;
  }

  .popup-row label {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: rgba(255, 255, 255, 0.7);
    font-size: 11px;
  }

  .popup-row label.full-width {
    flex: auto;
  }

  .popup-row input,
  .popup-row textarea {
    background: rgba(42, 42, 42, 0.8);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: rgba(255, 255, 255, 0.9);
    padding: 6px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-family: monospace; /* 時間入力を読みやすく */
  }

  .popup-row input:focus,
  .popup-row textarea:focus {
    outline: none;
    border-color: rgba(255, 193, 7, 0.8);
  }

  .popup-row input.error {
    border-color: #f44336;
    background: rgba(244, 67, 54, 0.1);
  }

  .overlap-warning {
    color: #f44336;
    font-size: 11px;
    margin-top: 4px;
    padding: 4px 8px;
    background: rgba(244, 67, 54, 0.1);
    border-radius: 4px;
    border-left: 3px solid #f44336;
  }

  .popup-row textarea {
    resize: vertical;
    font-family: inherit;
  }

  .popup-actions {
    display: flex;
    justify-content: flex-end;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .delete-button {
    background: rgba(244, 67, 54, 0.9);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    transition: all 0.2s;
  }

  .delete-button:hover {
    background: rgba(211, 47, 47, 0.95);
    border-color: rgba(255, 255, 255, 0.3);
    box-shadow: 0 4px 12px rgba(244, 67, 54, 0.3);
  }

  /* 追加用の丸いポップアップ */
  .add-popup {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 48px;
    height: 48px;
    background: rgba(76, 175, 80, 0.9);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow:
      0 4px 16px rgba(76, 175, 80, 0.4),
      0 0 0 1px rgba(255, 255, 255, 0.1);
    transition: all 0.2s;
    z-index: 1000;
  }

  .add-popup:hover {
    background: rgba(69, 160, 73, 0.95);
    transform: translate(-50%, -50%) scale(1.1);
    box-shadow:
      0 6px 20px rgba(76, 175, 80, 0.5),
      0 0 0 2px rgba(255, 255, 255, 0.15);
  }

  .add-icon {
    color: white;
    font-size: 28px;
    font-weight: bold;
    line-height: 1;
    user-select: none;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
