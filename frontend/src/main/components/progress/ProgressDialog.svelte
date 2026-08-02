<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import { crossfade } from 'svelte/transition';
  import { flip } from 'svelte/animate';
  import { quintOut, quintIn } from 'svelte/easing';
  import {
    fetchEditUploadStatus,
    updateEditUploadProcessOptions,
    cancelEditUploadProcess,
  } from '../../api/assets';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import type { EditUploadStatus, ProgressEvent, VideoAssetPayload } from '../../api/types';
  import { UploadCloud, Film, AlertTriangle, Youtube, SquareStack } from 'lucide-svelte';
  import {
    ProgressStateMachine,
    type ConnectionState,
    type ItemState,
  } from './progressStateMachine';
  import {
    PROGRESS_IMAGE_PRIORITY,
    ProgressImageLoader,
    type ProgressImageReady,
    type ProgressImageRequest,
  } from './progressImageLoader';
  import { pickResponsiveStage } from './responsiveStage';

  interface Props {
    isOpen?: boolean;
  }

  interface CompletedVideo {
    id: string;
    title: string;
    thumbnailSourceUrl: string;
    fallbackSourceUrl: string;
    dateLabel: string;
  }

  interface RequestedImageSlot {
    ownerId: string;
    slotId: string;
  }

  interface FlyingUploadBlock {
    key: string;
    blockIndex: number;
    flightIndex: number;
  }

  let { isOpen = $bindable(false) }: Props = $props();

  const sm = new ProgressStateMachine();
  const progressImageLoader = new ProgressImageLoader();
  let tasksVersion = $state(0);
  let readyImages = $state<Record<string, ProgressImageReady>>({});
  let requestedImageSlots = new Map<string, RequestedImageSlot>();

  function progressImageKey(ownerId: string, slotId: string): string {
    return `${ownerId}\u0000${slotId}`;
  }

  function setReadyImage(ownerId: string, slotId: string, image: ProgressImageReady): void {
    readyImages = { ...readyImages, [progressImageKey(ownerId, slotId)]: image };
  }

  function readyImageUrl(ownerId: string, slotId: string): string {
    return readyImages[progressImageKey(ownerId, slotId)]?.objectUrl ?? '';
  }

  function reconcileProgressImageRequests(requests: ProgressImageRequest[]): void {
    const nextSlots = new Map<string, RequestedImageSlot>();
    for (const request of requests) {
      const key = progressImageKey(request.ownerId, request.slotId);
      nextSlots.set(key, { ownerId: request.ownerId, slotId: request.slotId });
      progressImageLoader.request(request);
    }

    const nextReadyImages = { ...readyImages };
    for (const [key, slot] of requestedImageSlots) {
      if (nextSlots.has(key)) continue;
      progressImageLoader.releaseSlot(slot.ownerId, slot.slotId);
      delete nextReadyImages[key];
    }
    requestedImageSlots = nextSlots;
    readyImages = nextReadyImages;
  }

  let eventSource: EventSource | null = null;
  let messageHandler: ((event: MessageEvent) => void) | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let countdownTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectAttempt = $state(0);
  let retryCountdown = $state(0);

  let connectionState = $state<ConnectionState>('idle');
  let editUploadStatus = $state<EditUploadStatus | null>(null);
  let optionLoading = $state(false);
  let optionSaving = $state(false);
  let optionErrorMessage = $state('');
  let wasOpen = $state(false);
  let statusRequestId = $state(0);
  let cancelLoading = $state(false);

  // --- 本番UI向け追加状態 ---
  let currentStep = $state<
    'idle' | 'analyzing' | 'merging' | 'packaging' | 'uploading' | 'published'
  >('idle');

  // 結合時の秒数進行（実進捗と同期）
  let mergeProgressSeconds = $state(0);
  let mergeProgressItemIndex = $state<number | null>(null);
  let isResetting = $state(false);
  let prevActiveIndex = $state<number | null>(null);

  // 右側のアップロード待機リスト (自動編集が完了した動画がここに吸い込まれて蓄積される)
  let completedVideos = $state<CompletedVideo[]>([]);
  let lastPreviewSourceUrl = $state('');
  const lastPreviewImage = $derived.by(() => readyImageUrl('progress-dialog', 'main-stable'));
  let previewViewportWidth = $state(960);
  let previewViewportHeight = $state(540);
  let flyingUploadBlocks = $state<FlyingUploadBlock[]>([]);
  let visualUploadVideoId: string | null = null;
  let visualUploadBlockCount = $state(0);
  let uploadReceivedBlockCount = $state(0);
  let lastHandledUploadTargetBlockCount = 0;
  let uploadFlightSequence = 0;
  let uploadedVideoIds = $state<string[]>([]);
  const flyingUploadBlockTimers: ReturnType<typeof setTimeout>[] = [];

  const dialogMinHeight = 'min(75vh, 52rem)';
  const dialogMaxHeight = '95vh';
  const streamEventNames = ['progress_event', 'progress'];
  const progressFrameWidth = 960;
  const uploadGridSize = 10;
  const uploadBlockIndexes = Array.from({ length: uploadGridSize * uploadGridSize }, (_, i) => i);
  const uploadBlockRanks = uploadBlockIndexes
    .map((index) => {
      const col = index % uploadGridSize;
      const row = Math.floor(index / uploadGridSize);
      const center = (uploadGridSize - 1) / 2;
      const distance = Math.hypot(col - center, row - center);
      return { index, distance };
    })
    .sort((a, b) => a.distance - b.distance || a.index - b.index)
    .reduce<number[]>(
      (ranks, item, rank) => {
        ranks[item.index] = rank;
        return ranks;
      },
      Array(uploadGridSize * uploadGridSize).fill(0)
    );
  const uploadRankedBlockIndexes = [...uploadBlockIndexes].sort(
    (a, b) => uploadBlockRanks[a] - uploadBlockRanks[b]
  );

  // Svelteの crossfade トランジション（中央の完成サムネイル ➜ 右のカードへの移動）
  const [send, receive] = crossfade({
    duration: 600,
    easing: quintOut,
    fallback(_node) {
      return {
        duration: 400,
        easing: quintOut,
        css: (t) => `
          transform: scale(${t});
          opacity: ${t};
        `,
      };
    },
  });

  // tasksVersion が変化するたびに状態マシンから最新値を読み取る
  const taskList = $derived.by(() => {
    void tasksVersion;
    return sm.taskList;
  });
  const allFinished = $derived.by(() => {
    void tasksVersion;
    return sm.allFinished;
  });
  const anyRunning = $derived.by(() => {
    void tasksVersion;
    return sm.anyRunning;
  });

  const sleepAfterUploadEnabled = $derived(editUploadStatus?.sleepAfterUploadEffective ?? false);
  const sleepToggleDisabled = $derived(optionLoading || optionSaving || !editUploadStatus);

  // auto_edit タスクとアイテム情報
  const editTask = $derived(taskList.find((t) => t.id === 'auto_edit'));
  const uploadTask = $derived(taskList.find((t) => t.id === 'auto_upload'));
  const responsiveStage = $derived(
    pickResponsiveStage(editTask, uploadTask, completedVideos.length)
  );
  const editItems = $derived(editTask ? editTask.items : []);
  const activeIndex = $derived(editTask ? editTask.activeIndex : null);
  const currentItem = $derived(
    activeIndex !== null && editItems[activeIndex] ? editItems[activeIndex] : null
  );
  const mergeStepActive = $derived(currentItem?.activeStepKey === 'concat');
  const uploadStageExpanded = $derived.by(() => {
    return (
      responsiveStage === 'uploading' ||
      currentStep === 'uploading' ||
      currentStep === 'published' ||
      Boolean(editTask && editTask.status === 'succeeded' && completedVideos.length > 0)
    );
  });
  const youtubeAreaLabel = $derived(
    uploadStageExpanded ? 'YouTubeアップロードエリア 展開中' : 'YouTubeアップロードエリア 待機中'
  );
  const activeUploadVideo = $derived.by<CompletedVideo | null>(() => {
    if (completedVideos.length === 0) return null;
    const activeUploadItem =
      uploadTask && uploadTask.activeIndex !== null
        ? uploadTask.items[uploadTask.activeIndex]
        : null;
    if (activeUploadItem) {
      return (
        completedVideos.find((video) => video.title === activeUploadItem.title) ??
        completedVideos[0]
      );
    }
    return uploadStageExpanded ? completedVideos[0] : null;
  });
  const activeUploadProgressPercent = $derived.by(() => {
    void tasksVersion;
    if (!uploadTask || uploadTask.activeIndex === null || !activeUploadVideo) return 0;
    const activeItem = uploadTask.items[uploadTask.activeIndex];
    if (!activeItem) return 0;
    if (activeItem.status === 'success') return 100;
    if (hasUploadStepCompleted(activeItem)) return 100;
    if (activeItem.activeStepKey !== 'upload') return 0;
    return clampPercent(uploadTask.progressPercent ?? 0);
  });
  const uploadedUploadTitles = $derived.by(() => {
    void tasksVersion;
    const titles = new Set<string>();
    if (!uploadTask) return titles;
    uploadTask.items.forEach((item, index) => {
      if ((item.status === 'success' && item.dismissed) || index < uploadTask.completed) {
        titles.add(item.title);
      }
    });
    return titles;
  });
  const uploadTargetBlockCount = $derived(
    Math.floor((activeUploadProgressPercent / 100) * uploadBlockIndexes.length)
  );
  const uploadTransferredBlockCount = $derived(visualUploadBlockCount);
  const uploadReceiverBlockCount = $derived(uploadReceivedBlockCount);
  $effect(() => {
    const activeVideoId = activeUploadVideo?.id ?? null;
    const taskRunning = uploadTask?.status === 'running' && activeVideoId !== null;
    const targetBlockCount = uploadTargetBlockCount;

    untrack(() => {
      if (!taskRunning) {
        resetUploadTransfer(0, null);
        return;
      }

      if (visualUploadVideoId !== activeVideoId) {
        resetUploadTransfer(0, activeVideoId);
      } else if (targetBlockCount < visualUploadBlockCount) {
        resetUploadTransfer(targetBlockCount, activeVideoId);
      }

      if (
        targetBlockCount > lastHandledUploadTargetBlockCount &&
        visualUploadBlockCount < uploadBlockIndexes.length
      ) {
        lastHandledUploadTargetBlockCount = targetBlockCount;
        launchNextUploadBlock();
        return;
      }

      lastHandledUploadTargetBlockCount = targetBlockCount;
    });
  });

  $effect(() => {
    const uploadedTitles = uploadedUploadTitles;
    if (uploadedTitles.size === 0) return;

    untrack(() => {
      const uploadedVideos = completedVideos.filter((video) => uploadedTitles.has(video.title));
      if (uploadedVideos.length === 0) return;

      const nextUploadedIds = new Set(uploadedVideoIds);
      uploadedVideos.forEach((video) => nextUploadedIds.add(video.id));
      uploadedVideoIds = [...nextUploadedIds];
      completedVideos = completedVideos.filter((video) => !uploadedTitles.has(video.title));
    });
  });

  // 現在処理中のクリップアセットの配列
  const activeClips = $derived(currentItem?.clips?.video_assets ?? []);
  const activeMergeItemKey = $derived(
    currentItem && activeIndex !== null
      ? `${activeIndex}:${currentItem.clips?.video_assets[0]?.video_id ?? currentItem.title}`
      : ''
  );

  const totalDurationSeconds = $derived(
    activeClips.reduce((sum, clip) => sum + clip.duration_seconds, 0)
  );
  const visibleMergeProgressSeconds = $derived.by(() => {
    if (mergeStepActive && editTask && typeof editTask.progressPercent === 'number') {
      return (editTask.progressPercent / 100) * totalDurationSeconds;
    }
    return mergeProgressSeconds;
  });

  const clipCumulativeStarts = $derived.by(() => {
    return activeClips.reduce((acc, clip, idx) => {
      if (idx === 0) {
        acc.push(0);
      } else {
        acc.push(acc[idx - 1] + activeClips[idx - 1].duration_seconds);
      }
      return acc;
    }, [] as number[]);
  });

  // --- カスタムトランジション・表示用状態の定義 ---

  function slideFadeUp(node: HTMLElement, { duration = 700 }) {
    return {
      duration,
      easing: quintOut,
      css: (t: number) => {
        const opacity = t;
        const translateY = (1 - t) * -28;
        const height = t * node.offsetHeight;
        const marginBottom = t * parseFloat(getComputedStyle(node).marginBottom || '0');
        const paddingTop = t * parseFloat(getComputedStyle(node).paddingTop || '0');
        const paddingBottom = t * parseFloat(getComputedStyle(node).paddingBottom || '0');

        return `
          opacity: ${opacity};
          transform: translateY(${translateY}px);
          height: ${height}px;
          margin-bottom: ${marginBottom}px;
          padding-top: ${paddingTop}px;
          padding-bottom: ${paddingBottom}px;
          overflow: hidden;
        `;
      },
    };
  }

  const visibleEditItems = $derived.by(() => {
    void tasksVersion;
    return editItems.filter((item, idx) => {
      return !item.dismissed && (activeIndex === null || idx >= activeIndex);
    });
  });

  interface PreviewState {
    id: string;
    sourceUrl: string;
    image: string;
    isFinal: boolean;
    revealProgress: number;
    finalSettled: boolean;
    fallbackImage?: string;
    fallbackSourceUrl?: string;
    animatePushLeft?: boolean;
  }

  function clampRatio(value: number): number {
    return Math.min(1, Math.max(0, value));
  }

  function clampPercent(value: number): number {
    return Math.min(100, Math.max(0, value));
  }

  function hasUploadStepCompleted(item: ItemState): boolean {
    const uploadStep = item.steps.find((step) => step.key === 'upload');
    if (uploadStep?.status === 'success') return true;
    return ['caption', 'thumb', 'playlist', 'delete'].includes(item.activeStepKey ?? '');
  }

  function trackPreviewViewport(node: HTMLElement): { destroy: () => void } {
    const update = (): void => {
      const rect = node.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        previewViewportWidth = Math.max(1, Math.round(rect.width));
        previewViewportHeight = Math.max(1, Math.round(rect.height));
      }
    };

    update();

    if (typeof ResizeObserver === 'undefined') {
      return { destroy: () => {} };
    }

    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(node);
    return {
      destroy: () => resizeObserver.disconnect(),
    };
  }

  const finalThumbnailRevealProgress = $derived.by(() => {
    if (currentStep === 'published' || currentStep === 'uploading') return 1;
    if (currentStep !== 'packaging') return 1;
    const activeStepKey = currentItem?.activeStepKey;
    if (activeStepKey === 'save' || currentItem?.status === 'success') return 1;
    if (activeStepKey !== 'thumbnail') return 0;
    if (editTask && typeof editTask.progressPercent === 'number') {
      return clampRatio(editTask.progressPercent / 100);
    }
    return 0;
  });

  const finalThumbnailReady = $derived.by(() => {
    if (currentStep === 'published' || currentStep === 'uploading') return true;
    if (currentStep !== 'packaging') return false;
    const activeStepKey = currentItem?.activeStepKey;
    if (activeStepKey === 'save' || currentItem?.status === 'success') return true;
    if (activeStepKey !== 'thumbnail') return false;
    return editTask !== undefined && typeof editTask.progressPercent === 'number';
  });

  const activePreview = $derived.by<PreviewState | null>(() => {
    if (!currentItem) return null;
    const liveReady = readyImages[progressImageKey('progress-dialog', 'main-live')];
    const finalReady = readyImages[progressImageKey('progress-dialog', 'main-final')];
    const finalSourceUrl = finalThumbnailReady ? getEditedThumbnailUrl(currentItem) : '';
    const ready = finalReady?.sourceUrl === finalSourceUrl ? finalReady : liveReady;
    if (!ready) return null;

    const videoId = currentItem.clips?.video_assets[0]?.video_id ?? `group_${activeIndex}`;
    const isFinalImage = Boolean(finalSourceUrl && ready.sourceUrl === finalSourceUrl);
    const revealProgress = isFinalImage ? finalThumbnailRevealProgress : 1;
    return {
      id: videoId,
      sourceUrl: ready.sourceUrl,
      image: ready.objectUrl,
      isFinal: isFinalImage,
      revealProgress,
      finalSettled: isFinalImage && revealProgress >= 1,
      fallbackImage: isFinalImage ? liveReady?.objectUrl : undefined,
      fallbackSourceUrl: isFinalImage ? liveReady?.sourceUrl : undefined,
    };
  });

  let previewList = $state<PreviewState[]>([]);
  const hasPreviewImage = $derived(
    previewList.some((preview) => Boolean(preview.image || preview.fallbackImage))
  );

  function pushLeftIn(node: HTMLElement, options: { animate?: boolean }) {
    if (!options?.animate) {
      return { duration: 0 };
    }
    return {
      duration: 600,
      easing: quintIn,
      css: (t: number) => {
        const translate = (1 - t) * 100;
        return `
          transform: translateX(${translate}%);
          position: absolute;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
        `;
      },
    };
  }

  function pushLeftOut(node: HTMLElement, options: { animate?: boolean }) {
    if (!options?.animate) {
      return { duration: 0 };
    }
    return {
      duration: 600,
      easing: quintIn,
      css: (t: number) => {
        const translate = (t - 1) * 100;
        return `
          transform: translateX(${translate}%);
          position: absolute;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
        `;
      },
    };
  }

  let prevPreviewImage = '';
  let prevPreviewIsFinal = false;

  $effect(() => {
    const current = activePreview;
    untrack(() => {
      if (!isOpen) {
        previewList = [];
        lastPreviewSourceUrl = '';
        prevPreviewImage = '';
        prevPreviewIsFinal = false;
        return;
      }
      if (current) {
        const stablePreviewSourceUrl = current.fallbackSourceUrl || current.sourceUrl;
        if (stablePreviewSourceUrl) {
          lastPreviewSourceUrl = stablePreviewSourceUrl;
        }

        const imageChanged = current.image !== prevPreviewImage;
        let animatePushLeft = false;

        if (imageChanged) {
          if (prevPreviewImage !== '' && !prevPreviewIsFinal && !current.isFinal) {
            animatePushLeft = true;
          }
          prevPreviewImage = current.image;
          prevPreviewIsFinal = current.isFinal;
        }

        const previewWithAnim: PreviewState = {
          ...current,
          animatePushLeft,
        };

        const exists = previewList.some((p) => p.id === current.id);
        if (!exists) {
          previewList = [previewWithAnim];
        } else {
          previewList = previewList.map((p) => (p.id === current.id ? previewWithAnim : p));
        }
      } else {
        if (previewList.length > 0) {
          previewList = [];
        }
        prevPreviewImage = '';
        prevPreviewIsFinal = false;
      }
    });
  });

  function backgroundImageStyle(image: string | undefined): string {
    if (!image) return '';
    return `background-image: url("${image.replace(/"/g, '\\"')}");`;
  }

  function thumbnailBlockStyle(image: string | undefined, index: number): string {
    if (!image) return '';
    const col = index % uploadGridSize;
    const row = Math.floor(index / uploadGridSize);
    const positionX = uploadGridSize > 1 ? (col / (uploadGridSize - 1)) * 100 : 0;
    const positionY = uploadGridSize > 1 ? (row / (uploadGridSize - 1)) * 100 : 0;
    return [
      `background-image: url("${image.replace(/"/g, '\\"')}")`,
      `background-size: ${uploadGridSize * 100}% ${uploadGridSize * 100}%`,
      `background-position: ${positionX}% ${positionY}%`,
    ].join('; ');
  }

  function flyingBlockStyle(image: string | undefined, index: number, flightIndex: number): string {
    const verticalOffset = (flightIndex - 3) * 0.46;
    const startOffset = verticalOffset * -0.25;
    const arcOffset = -0.85 - (flightIndex % 2) * 0.22;
    const rotation = ((index % 5) - 2) * 9;
    return [
      thumbnailBlockStyle(image, index),
      `--flight-index: ${flightIndex}`,
      `--flight-y: ${verticalOffset.toFixed(2)}rem`,
      `--flight-start-y: ${startOffset.toFixed(2)}rem`,
      `--flight-arc: ${arcOffset.toFixed(2)}rem`,
      `--flight-rotate: ${rotation.toFixed(0)}deg`,
      `--flight-rotate-start: ${(rotation * -1).toFixed(0)}deg`,
      '--flight-delay: 0s',
    ].join('; ');
  }

  function clearFlyingUploadBlockTimers(): void {
    while (flyingUploadBlockTimers.length > 0) {
      const timer = flyingUploadBlockTimers.pop();
      if (timer) {
        clearTimeout(timer);
      }
    }
  }

  function resetUploadTransfer(blockCount: number, videoId: string | null): void {
    clearFlyingUploadBlockTimers();
    flyingUploadBlocks = [];
    visualUploadBlockCount = blockCount;
    uploadReceivedBlockCount = blockCount;
    lastHandledUploadTargetBlockCount = blockCount;
    visualUploadVideoId = videoId;
  }

  function launchNextUploadBlock(): void {
    const rank = visualUploadBlockCount;
    const blockIndex = uploadRankedBlockIndexes[rank % uploadRankedBlockIndexes.length];
    const flightIndex = rank % 7;
    const block: FlyingUploadBlock = {
      key: `${visualUploadVideoId ?? activeUploadVideo?.id ?? 'upload'}:${rank}:${uploadFlightSequence++}`,
      blockIndex,
      flightIndex,
    };

    visualUploadBlockCount = Math.min(uploadBlockIndexes.length, visualUploadBlockCount + 1);
    flyingUploadBlocks = [...flyingUploadBlocks, block];

    const arrivalTimer = setTimeout(() => {
      uploadReceivedBlockCount = Math.max(
        uploadReceivedBlockCount,
        Math.min(uploadBlockIndexes.length, rank + 1)
      );
    }, 1220);
    flyingUploadBlockTimers.push(arrivalTimer);

    const timer = setTimeout(() => {
      flyingUploadBlocks = flyingUploadBlocks.filter((item) => item.key !== block.key);
    }, 1320);
    flyingUploadBlockTimers.push(timer);
  }

  function isUploadBlockTransferredFromSource(index: number): boolean {
    return uploadBlockRanks[index] < uploadTransferredBlockCount;
  }

  function isUploadBlockReceived(index: number): boolean {
    return uploadBlockRanks[index] < uploadReceiverBlockCount;
  }

  function isActiveUploadVideo(video: CompletedVideo): boolean {
    return uploadTask?.status === 'running' && activeUploadVideo?.id === video.id;
  }

  function finalThumbnailStyle(preview: PreviewState): string {
    if (!preview.isFinal) return '';
    const reveal = clampRatio(preview.revealProgress);
    const width = Math.max(1, previewViewportWidth);
    const height = Math.max(1, previewViewportHeight);
    const totalPixels = width * height;
    const revealedPixels = Math.min(totalPixels, Math.max(0, Math.floor(totalPixels * reveal)));
    const completeRows = Math.min(height, Math.floor(revealedPixels / width));
    const currentRowWidth = completeRows >= height ? 0 : revealedPixels - completeRows * width;
    const currentRowHeight = currentRowWidth > 0 && completeRows < height ? 1 : 0;
    return [
      `--pixel-reveal-progress: ${reveal.toFixed(3)}`,
      `--pixel-reveal-complete-height: ${completeRows}px`,
      `--pixel-reveal-current-row-top: ${completeRows}px`,
      `--pixel-reveal-current-width: ${currentRowWidth}px`,
      `--pixel-reveal-row-height: ${currentRowHeight}px`,
    ].join('; ');
  }

  function previewWrapperStyle(preview: PreviewState): string {
    return [backgroundImageStyle(preview.fallbackImage), finalThumbnailStyle(preview)]
      .filter(Boolean)
      .join('; ');
  }

  function completedVideoImage(video: CompletedVideo): string {
    const ownerId = `completed:${video.id}`;
    return readyImageUrl(ownerId, 'final-thumbnail') || readyImageUrl(ownerId, 'fallback');
  }

  // 進捗イベントからフェーズの状態を判定する
  $effect(() => {
    const uploadTask = taskList.find((t) => t.id === 'auto_upload');

    if (allFinished) {
      currentStep = 'published';
    } else if (uploadTask && uploadTask.status === 'running') {
      currentStep = 'uploading';
    } else if (editTask && editTask.status === 'running') {
      if (
        currentItem &&
        (currentItem.activeStepKey === 'edit_group' || currentItem.status === 'pending')
      ) {
        currentStep = 'analyzing';
      } else if (currentItem && currentItem.activeStepKey === 'concat') {
        currentStep = 'merging';
      } else {
        currentStep = 'packaging';
      }
    } else {
      currentStep = 'idle';
    }
  });

  // 結合中の再生ヘッドの進捗率（実進捗と同期）
  $effect(() => {
    if (mergeStepActive) {
      const itemChanged = mergeProgressItemIndex !== activeIndex;
      if (itemChanged) {
        mergeProgressItemIndex = activeIndex;
      }
      const currentSeconds = itemChanged ? 0 : mergeProgressSeconds;
      if (editTask && typeof editTask.progressPercent === 'number') {
        // SSE 経由の実結合進捗率(0～100)から進行秒数を逆算
        const targetSec = (editTask.progressPercent / 100) * totalDurationSeconds;
        // 同じタイムスケジュール内だけ進捗が戻らないように保護する
        mergeProgressSeconds = Math.max(currentSeconds, targetSec);
      } else {
        // 初期のフォールバック
        const activeIdx = editTask?.activeIndex ?? 0;
        const completedSec = clipCumulativeStarts[activeIdx] ?? 0;
        mergeProgressSeconds = Math.max(currentSeconds, completedSec);
      }
    } else {
      if (
        currentStep === 'packaging' ||
        currentStep === 'uploading' ||
        currentStep === 'published'
      ) {
        mergeProgressSeconds = totalDurationSeconds;
      } else {
        if (currentStep === 'idle' || !activeMergeItemKey) {
          mergeProgressItemIndex = activeIndex;
        }
        mergeProgressSeconds = 0;
      }
    }
  });

  // タイムスケジュール（動画編集アイテム）の切り替えを検知して一時的に transition を無効化する
  $effect(() => {
    if (activeIndex !== prevActiveIndex) {
      isResetting = true;
      prevActiveIndex = activeIndex;
      const timer = setTimeout(() => {
        isResetting = false;
      }, 50);
      return () => clearTimeout(timer);
    }
  });

  // 再生ヘッドの現在位置と画像を決定
  const currentMergingInfo = $derived.by(() => {
    const progressSeconds = visibleMergeProgressSeconds;
    if (currentStep !== 'merging' && progressSeconds === 0) {
      const firstClip = activeClips[0];
      const defaultImg = firstClip ? buildProgressFrameUrl(firstClip.video_id, 0) : '';
      return { clipIndex: 0, secondsInClip: 0, percent: 0, image: defaultImg };
    }

    let clipIndex = activeClips.length - 1;
    for (let i = 0; i < clipCumulativeStarts.length; i++) {
      if (progressSeconds < clipCumulativeStarts[i] + activeClips[i].duration_seconds) {
        clipIndex = i;
        break;
      }
    }

    const startSec = clipCumulativeStarts[clipIndex] ?? 0;
    const secondsInClip = progressSeconds - startSec;
    const clip = activeClips[clipIndex];

    // 最初の1分間は、現在処理中のクリップに関わらず、一番最初の動画（activeClips[0]）の最初の場面（t=0）を表示する
    const targetClip = progressSeconds < 60 ? activeClips[0] : clip;
    const targetSeconds = targetClip
      ? progressSeconds < 60
        ? 0
        : getMinuteFrameSeconds(secondsInClip, targetClip)
      : 0;
    const image = targetClip ? buildProgressFrameUrl(targetClip.video_id, targetSeconds) : '';

    const percent = totalDurationSeconds > 0 ? (progressSeconds / totalDurationSeconds) * 100 : 0;

    return { clipIndex, secondsInClip, percent, image };
  });

  // 完成サムネイルの動的URL再構成
  function getEditedThumbnailUrl(item: ItemState): string {
    if (!item.clips) return '';
    const clips = item.clips;
    if (clips.thumbnail_filename) {
      return `/thumbnails/edited/${encodeURIComponent(clips.thumbnail_filename)}`;
    }
    const firstVideoName = clips.video_assets[0]?.video_id ?? '';
    const yearMatch = firstVideoName.match(/(\d{4})\d{4}_\d{4}/);
    const year = yearMatch ? yearMatch[1] : '2026';

    const dateMatch = clips.date_label.match(/(\d{2})\/(\d{2})\s+(\d{2}):/);
    if (dateMatch) {
      const yyyymmdd = `${year}${dateMatch[1]}${dateMatch[2]}`;
      const hh = dateMatch[3];
      // 拡張子は backend の generate_filename の慣例に則る（通常mp4/mkvだがサムネイル画像は常にpng）
      const name = `${yyyymmdd}_${hh}_${clips.match_name}_${clips.rule_name}.png`;
      return `/thumbnails/edited/${encodeURIComponent(name)}`;
    }
    return '';
  }

  function buildProgressImageRequests(): ProgressImageRequest[] {
    const requests: ProgressImageRequest[] = [];
    let sequence = 0;
    const addRequest = (
      ownerId: string,
      slotId: string,
      url: string,
      priority: ProgressImageRequest['priority']
    ): void => {
      if (!url) return;
      requests.push({
        ownerId,
        slotId,
        url,
        priority,
        sequence: sequence++,
        onReady: (image) => setReadyImage(ownerId, slotId, image),
        onError: (error) => {
          void error;
        },
      });
    };

    addRequest(
      'progress-dialog',
      'main-live',
      currentMergingInfo.image,
      PROGRESS_IMAGE_PRIORITY.MAIN
    );
    const finalSourceUrl =
      currentItem && finalThumbnailReady ? getEditedThumbnailUrl(currentItem) : '';
    addRequest('progress-dialog', 'main-final', finalSourceUrl, PROGRESS_IMAGE_PRIORITY.MAIN);
    addRequest(
      'progress-dialog',
      'main-stable',
      lastPreviewSourceUrl,
      PROGRESS_IMAGE_PRIORITY.MAIN
    );

    for (const item of visibleEditItems) {
      const itemIndex = editItems.indexOf(item);
      const ownerId = `edit-item:${item.clips?.video_assets[0]?.video_id ?? item.title}`;
      const clips = item.clips?.video_assets ?? [];
      for (const [clipIndex, clip] of clips.entries()) {
        let priority: ProgressImageRequest['priority'] = PROGRESS_IMAGE_PRIORITY.LATER_ITEM;
        if (itemIndex === activeIndex && clipIndex === currentMergingInfo.clipIndex) {
          priority = PROGRESS_IMAGE_PRIORITY.ACTIVE_CLIP;
        } else if (itemIndex === activeIndex) {
          priority = PROGRESS_IMAGE_PRIORITY.ACTIVE_ITEM_REMAINDER;
        } else if (activeIndex !== null && itemIndex === activeIndex + 1) {
          priority = PROGRESS_IMAGE_PRIORITY.NEXT_ITEM;
        }
        addRequest(
          ownerId,
          `clip:${clipIndex}:${clip.video_id}`,
          buildProgressFrameUrl(clip.video_id, getReusableClipFrameSeconds(clip)),
          priority
        );
      }
    }

    for (const video of completedVideos) {
      const ownerId = `completed:${video.id}`;
      addRequest(ownerId, 'fallback', video.fallbackSourceUrl, PROGRESS_IMAGE_PRIORITY.LATER_ITEM);
      addRequest(
        ownerId,
        'final-thumbnail',
        video.thumbnailSourceUrl,
        PROGRESS_IMAGE_PRIORITY.LATER_ITEM
      );
    }
    return requests;
  }

  // 自動編集完了を検知して待機エリアへアペンド
  $effect(() => {
    if (!editItems) return;
    editItems.forEach((item, idx) => {
      if (item.status === 'success' && item.dismissed) {
        const videoId = item.clips?.video_assets[0]?.video_id ?? `group_${idx}`;
        if (
          !completedVideos.some((v) => v.id === videoId) &&
          !uploadedVideoIds.includes(videoId) &&
          !uploadedUploadTitles.has(item.title)
        ) {
          const liveReady = readyImages[progressImageKey('progress-dialog', 'main-live')];
          completedVideos = [
            ...completedVideos,
            {
              id: videoId,
              title: item.title,
              thumbnailSourceUrl: getEditedThumbnailUrl(item),
              fallbackSourceUrl: liveReady?.sourceUrl ?? '',
              dateLabel: item.clips?.date_label.replace('\n', ' ') ?? '',
            },
          ];
        }
      }
    });
  });

  $effect(() => {
    const open = isOpen;
    void visibleEditItems;
    void activeIndex;
    void currentMergingInfo;
    void finalThumbnailReady;
    void completedVideos;
    const requests = open ? buildProgressImageRequests() : [];

    untrack(() => {
      if (!open) {
        progressImageLoader.clear();
        requestedImageSlots.clear();
        readyImages = {};
        lastPreviewSourceUrl = '';
        return;
      }
      reconcileProgressImageRequests(requests);
    });
  });

  // レート値の変更を追跡してピン留め表示するリストを生成
  function getRateTags(clips: VideoAssetPayload[]) {
    const tags = [];
    let lastRateStr: string | null = null;
    let hasFoundFirst = false;

    for (let i = 0; i < clips.length; i++) {
      const clip = clips[i];
      if (clip.rate) {
        const currentRateStr = clip.rate.value;
        if (!hasFoundFirst) {
          tags.push({
            clipIndex: i,
            value: `${clip.rate.type} ${clip.rate.value}`,
          });
          lastRateStr = currentRateStr;
          hasFoundFirst = true;
        } else if (lastRateStr !== currentRateStr) {
          tags.push({
            clipIndex: i,
            value: `${clip.rate.type} ${clip.rate.value}`,
          });
          lastRateStr = currentRateStr;
        }
      }
    }
    return tags;
  }

  // 1本あたりのクリップブロックの累積開始パーセンテージを計算するヘルパー
  function getClipLeftPercent(idx: number, clips: VideoAssetPayload[]): number {
    const total = clips.reduce((sum, c) => sum + c.duration_seconds, 0);
    if (total === 0) return 0;
    const startSec = clips.slice(0, idx).reduce((sum, c) => sum + c.duration_seconds, 0);
    return (startSec / total) * 100;
  }

  function buildProgressFrameUrl(videoId: string, seconds: number): string {
    const normalizedSeconds = Math.max(0, Math.floor(seconds));
    return `/api/assets/recorded/${encodeURIComponent(
      videoId
    )}/frame?t=${normalizedSeconds}&w=${progressFrameWidth}`;
  }

  function getReusableClipFrameSeconds(clip: VideoAssetPayload): number {
    const lastSecond = Math.max(0, Math.floor(clip.duration_seconds) - 1);
    return Math.min(60, lastSecond);
  }

  function getMinuteFrameSeconds(secondsInClip: number, clip: VideoAssetPayload): number {
    const lastSecond = Math.max(0, Math.floor(clip.duration_seconds) - 1);
    const minuteSecond = Math.max(0, Math.floor(secondsInClip / 60) * 60);
    return Math.min(minuteSecond, lastSecond);
  }

  // レートの文字色クラス判定
  function getRateColorClass(matchName: string | undefined): string {
    if (!matchName) return '';
    if (matchName === 'Xマッチ') return 'rate-x';
    if (matchName === 'バンカラマッチ') return 'rate-bankara';
    if (
      matchName.includes('イベント') ||
      matchName.includes('リーグ') ||
      matchName.includes('フェス')
    ) {
      return 'rate-event';
    }
    return '';
  }

  $effect(() => {
    if (isOpen) {
      ensureStream();
    } else {
      pauseStream();
    }
  });

  $effect(() => {
    if (isOpen !== wasOpen) {
      wasOpen = isOpen;
      if (isOpen) {
        optionErrorMessage = '';
        completedVideos = [];
        uploadedVideoIds = [];
        resetUploadTransfer(0, null);
        void loadEditUploadStatus();
      } else {
        optionErrorMessage = '';
        optionLoading = false;
        optionSaving = false;
      }
    }
  });

  // 日本語ステージ名へのマッピング定義
  const STAGE_TRANSLATIONS: Record<string, string> = {
    SCORCH_GORGE: 'ユノハナ大渓谷',
    EELTAIL_ALLEY: 'ゴンズイ地区',
    HAGGLEFISH_MARKET: 'ヤガラ市場',
    UNDERTOW_SPILLWAY: 'マテガイ放水路',
    MINCEMEAT_METALWORKS: 'ナメロウ金属',
    MAHI_MAHI_RESORT: 'マヒマヒリゾート＆スパ',
    MUSEUM_D_ALFONSINO: 'キンメダイ美術館',
    HAMMERHEAD_BRIDGE: 'マサバ海峡大橋',
    INKBLOT_ART_ACADEMY: '海女美術大学',
    STURGEON_SHIPYARD: 'チョウザメ造船',
    MAKO_MART: 'ザトウマーケット',
    WAHOO_WORLD: 'スメーシーワールド',
    FLOUNDER_HEIGHTS: 'ヒラメが丘団地',
    BRINEWATER_SPRINGS: 'クサヤ温泉',
    UMAMI_RUINS: 'ナンプラー遺跡',
    MANTA_MARIA: 'マンタマリア号',
    BARNACLE_AND_DIME: 'タラポートショッピングパーク',
    HUMPBACK_PUMP_TRACK: 'コンブトラック',
    CRABLEG_CAPITAL: 'タカアシ経済特区',
    SHIPSHAPE_CARGO_CO: 'オヒョウ海運',
    ROBO_ROM_EN: 'バイガイ亭',
    BLUEFIN_DEPOT: 'ネギトロ炭鉱',
    MARLIN_AIRPORT: 'カジキ空港',
    LEMURIA_HUB: 'リュウグウターミナル',
    URCHIN_UNDERPASS: 'デカライン高架下',
    scorch_gorge: 'ユノハナ大渓谷',
    eeltail_alley: 'ゴンズイ地区',
    hagglefish_market: 'ヤガラ市場',
    undertow_spillway: 'マテガイ放水路',
    mincemeat_metalworks: 'ナメロウ金属',
    mahi_mahi_resort: 'マヒマヒリゾート＆スパ',
    museum_d_alfonsino: 'キンメダイ美術館',
    hammerhead_bridge: 'マサバ海峡大橋',
    inkblot_art_academy: '海女美術大学',
    sturgeon_shipyard: 'チョウザメ造船',
    mako_mart: 'ザトウマーケット',
    wahoo_world: 'スメーシーワールド',
    flounder_heights: 'ヒラメが丘団地',
    brinewater_springs: 'クサヤ温泉',
    umami_ruins: 'ナンプラー遺跡',
    manta_maria: 'マンタマリア号',
    barnacle_and_dime: 'タラポートショッピングパーク',
    humpback_pump_track: 'コンブトラック',
    crableg_capital: 'タカアシ経済特区',
    shipshape_cargo_co: 'オヒョウ海運',
    robo_rom_en: 'バイガイ亭',
    bluefin_depot: 'ネギトロ炭鉱',
    marlin_airport: 'カジキ空港',
    lemuria_hub: 'リュウグウターミナル',
    urchin_underpass: 'デカライン高架下',
  };

  function getStageDisplayName(stageName: string | undefined): string {
    if (!stageName) return 'バトルステージ';
    return (
      STAGE_TRANSLATIONS[stageName] || STAGE_TRANSLATIONS[stageName.toUpperCase()] || stageName
    );
  }

  onDestroy(() => {
    progressImageLoader.dispose();
    disposeStream();
    sm.dispose();
    clearFlyingUploadBlockTimers();
  });

  function ensureStream(): void {
    if (eventSource) {
      return;
    }
    openStream();
  }

  function openStream(): void {
    shutdownStream(false);
    connectionState = 'connecting';
    try {
      const source = new EventSource('/api/events/progress');
      messageHandler = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as ProgressEvent;
          if (!payload || typeof payload.task_id !== 'string') {
            return;
          }
          applyEvent(payload);
        } catch (error) {
          console.error('progress-event-parse-failed', error);
        }
      };
      streamEventNames.forEach((name) => {
        source.addEventListener(name, messageHandler as EventListener);
      });
      source.onopen = () => {
        connectionState = 'open';
        reconnectAttempt = 0;
        resetCountdown();
      };
      source.onerror = () => {
        connectionState = 'error';
        shutdownStream(false);
        if (isOpen) {
          scheduleReconnect();
        }
      };
      eventSource = source;
    } catch {
      connectionState = 'error';
      shutdownStream(false);
      if (isOpen) {
        scheduleReconnect();
      }
    }
  }

  function pauseStream(): void {
    shutdownStream(true);
    connectionState = 'idle';
  }

  function disposeStream(): void {
    shutdownStream(true);
  }

  function shutdownStream(resetAttempts: boolean): void {
    if (eventSource) {
      streamEventNames.forEach((name) => {
        if (messageHandler && eventSource) {
          eventSource.removeEventListener(name, messageHandler as EventListener);
        }
      });
      eventSource.onopen = null;
      eventSource.onerror = null;
      eventSource.close();
    }
    eventSource = null;
    messageHandler = null;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    reconnectTimer = null;
    resetCountdown();
    if (resetAttempts) {
      reconnectAttempt = 0;
      retryCountdown = 0;
    }
  }

  function scheduleReconnect(): void {
    if (reconnectTimer || !isOpen) {
      return;
    }
    reconnectAttempt += 1;
    const delay = Math.min(15000, 2000 * reconnectAttempt);
    retryCountdown = Math.ceil(delay / 1000);
    resetCountdown();
    countdownTimer = setInterval(() => {
      if (retryCountdown > 0) {
        retryCountdown -= 1;
      } else {
        resetCountdown();
      }
    }, 1000);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      resetCountdown();
      if (isOpen) {
        openStream();
      }
    }, delay);
  }

  function resetCountdown(): void {
    if (countdownTimer) {
      clearInterval(countdownTimer);
    }
    countdownTimer = null;
    if (!reconnectTimer) {
      retryCountdown = 0;
    }
  }

  async function loadEditUploadStatus(): Promise<void> {
    const requestId = ++statusRequestId;
    optionLoading = true;
    try {
      const status = await fetchEditUploadStatus();
      if (requestId !== statusRequestId) {
        return;
      }
      editUploadStatus = status;
      optionErrorMessage = '';
    } catch (error) {
      if (requestId !== statusRequestId) {
        return;
      }
      optionErrorMessage =
        error instanceof Error ? error.message : 'オプションの取得に失敗しました。';
    } finally {
      if (requestId === statusRequestId) {
        optionLoading = false;
      }
    }
  }

  async function handleSleepAfterUploadChange(event: Event): Promise<void> {
    if (sleepToggleDisabled) {
      return;
    }
    const target = event.currentTarget as HTMLInputElement;
    const nextValue = target.checked;

    optionSaving = true;
    optionErrorMessage = '';
    try {
      editUploadStatus = await updateEditUploadProcessOptions({
        sleepAfterUpload: nextValue,
      });
    } catch (error) {
      optionErrorMessage =
        error instanceof Error ? error.message : 'オプションの更新に失敗しました。';
      target.checked = sleepAfterUploadEnabled;
      void loadEditUploadStatus();
    } finally {
      optionSaving = false;
    }
  }

  async function handleCancelProcess(): Promise<void> {
    if (!anyRunning || cancelLoading) return;
    cancelLoading = true;
    try {
      await cancelEditUploadProcess();
      isOpen = false; // キャンセル成功時は即座にダイアログを閉じる
    } catch (error) {
      optionErrorMessage =
        error instanceof Error ? error.message : 'キャンセルの要求に失敗しました。';
    } finally {
      cancelLoading = false;
    }
  }

  function applyEvent(event: ProgressEvent): void {
    const isStart = event.kind === 'start';
    sm.applyEvent(event);
    tasksVersion++;
    if (
      isStart &&
      isOpen &&
      !optionSaving &&
      !optionLoading &&
      (!editUploadStatus || editUploadStatus.state !== 'running')
    ) {
      void loadEditUploadStatus();
    }
  }

  function manualReconnect(): void {
    if (!isOpen) {
      return;
    }
    shutdownStream(false);
    resetCountdown();
    openStream();
  }

  const closeDisabled = $derived(anyRunning);

  function handleClose(): void {
    if (closeDisabled) {
      return;
    }
    isOpen = false;
  }
</script>

<BaseDialog
  bind:open={isOpen}
  title="進捗"
  showHeader={true}
  showFooter={true}
  footerVariant="custom"
  mobileFullscreen={true}
  maxWidth="min(1880px, calc(100vw - 2rem))"
  maxHeight={dialogMaxHeight}
  minHeight={dialogMinHeight}
  onClose={handleClose}
>
  <section class="dialog-body neon-abyss-theme" data-testid="progress-scroll-body">
    <!-- 接続エラー表示 (最小化ヘッダー警告) -->
    {#if connectionState === 'error'}
      <div class="connection-mini-alert" role="alert">
        <AlertTriangle size={16} />
        <span
          >通信切断。{#if retryCountdown > 0}{retryCountdown}秒後に自動接続...{:else}接続しています...{/if}</span
        >
        <button type="button" class="mini-retry-btn" onclick={manualReconnect}>今すぐ再接続</button>
      </div>
    {/if}

    <!-- 画面には表示しないが、アクセシビリティおよびE2Eテスト用に現在のフェーズを表すナビゲーション -->
    <nav aria-label="処理フェーズ" class="sr-only">
      <ul>
        <li class:active={currentStep === 'idle'}>待機</li>
        <li class:active={currentStep === 'analyzing'}>解析</li>
        <li class:active={currentStep === 'merging'}>結合</li>
        <li class:active={currentStep === 'packaging'}>パッケージ</li>
        <li class:active={currentStep === 'uploading'}>アップロード</li>
        <li class:active={currentStep === 'published'}>完了</li>
      </ul>
    </nav>

    <!-- メインパイプライン領域 (編集 → 待機 → YouTube) -->
    <main class="wf-pipeline" class:upload-stage-expanded={uploadStageExpanded}>
      <!-- 1. 中央：編集・動画成長エリア (Video Assembly - 中央) -->
      <section
        class="wf-panel assembly-panel"
        class:responsive-stage-active={responsiveStage === 'editing'}
        aria-label="1. 編集"
        aria-current={responsiveStage === 'editing' ? 'step' : undefined}
      >
        <div class="panel-header stage-panel-header assembly-header">
          <div class="panel-title-group">
            <div
              class="pipeline-stage-icon editing-stage-icon"
              role="img"
              aria-label="編集中エリア"
            >
              <Film size={22} />
            </div>
            <h3 class="stage-title" aria-label="1. 編集">
              <span class="stage-number">1.</span>
              <span class="stage-name">編集</span>
            </h3>
          </div>
        </div>
        <div class="assembly-monitor glass-surface">
          <!-- マッチ・ルール共通メタデータ表示領域 (動画枠外、直上、左揃え) -->
          {#if currentItem}
            <div class="common-metadata-overlay paintball-font">
              <span class="meta-label">MATCH:</span>
              <span class="meta-value glow-cyan"
                >{currentItem.clips?.match_name ?? 'バンカラマッチ'}</span
              >
              <span class="meta-separator">/</span>
              <span class="meta-label">RULE:</span>
              <span class="meta-value glow-cyan"
                >{currentItem.clips?.rule_name ?? 'ガチエリア'}</span
              >
            </div>
          {/if}

          <!-- ビデオプレビュー画面 -->
          <div
            class="video-preview-window"
            class:has-preview-backdrop={Boolean(lastPreviewImage)}
            style={backgroundImageStyle(lastPreviewImage)}
            use:trackPreviewViewport
          >
            {#if hasPreviewImage || lastPreviewImage}
              <div class="preview-container">
                {#if previewList.length === 0 && lastPreviewImage}
                  <img
                    class="preview-bg"
                    src={lastPreviewImage}
                    alt="Preview Frame"
                    data-testid="progress-main-image"
                  />
                {/if}
                {#each previewList as p (p.id)}
                  {#if p.isFinal}
                    <!-- svelte:crossfade 向けキーのバインド（待機エリアへの吸い込み用） -->
                    <div
                      class="preview-animation-wrapper"
                      class:final-settled={p.finalSettled}
                      style={previewWrapperStyle(p)}
                      out:send={{ key: p.id }}
                    >
                      <img
                        class="preview-bg preview-final"
                        src={p.image || p.fallbackImage || ''}
                        alt="Final Thumbnail"
                        data-testid="progress-main-image"
                      />
                    </div>
                  {:else}
                    <!-- 結合中の1分ごと表示 -->
                    {#key p.image}
                      <img
                        class="preview-bg"
                        src={p.image}
                        alt="Preview Frame"
                        data-testid="progress-main-image"
                        in:pushLeftIn={{ animate: p.animatePushLeft }}
                        out:pushLeftOut={{ animate: p.animatePushLeft }}
                      />
                    {/key}
                  {/if}
                {/each}
              </div>
            {:else}
              <div class="video-preview-empty">
                <Film size={48} class="muted-icon" />
                <p>動画結合を開始します...</p>
              </div>
            {/if}
          </div>

          <!-- マルチシークバーエリア（タイムスケジュールごとに縦並び） -->
          <div class="multi-timeline-area">
            {#if editItems.length === 0}
              <div class="empty-timeline-placeholder">
                <span>編集対象グループがありません</span>
              </div>
            {/if}

            {#each visibleEditItems as item (item.clips?.video_assets[0]?.video_id ?? item.title)}
              {@const isCurrent = activeIndex !== null && editItems[activeIndex] === item}
              {@const clips = item.clips?.video_assets ?? []}

              <div
                class="timeline-row"
                class:active={isCurrent}
                animate:flip={{ duration: 700 }}
                in:slideFadeUp={{ duration: 700 }}
              >
                <!-- 上部の日時表示 -->
                <div class="timeline-date-header paintball-font" class:active={isCurrent}>
                  {item.clips?.date_label
                    ? item.clips.date_label.replace('\n', ' ')
                    : '06/27 00:00～'}
                </div>

                <!-- シークバーとインジケーター全体 -->
                <div class="timeline-track-wrapper" class:no-transition={isResetting}>
                  <!-- レートピン留め表示 (バトルクリップのすぐ上に配置) -->
                  {#if isCurrent && clips.length > 0}
                    {#each getRateTags(clips) as tag}
                      {@const tagLeft = getClipLeftPercent(tag.clipIndex, clips)}
                      <div
                        class="timeline-rate-tag paintball-font {getRateColorClass(
                          item.clips?.match_name
                        )}"
                        style={`left: ${tagLeft}%;`}
                      >
                        {tag.value}
                      </div>
                    {/each}
                  {/if}

                  <div class="timeline-track glass-surface" class:inactive={!isCurrent}>
                    <!-- クリップブロック -->
                    {#each clips as clip, clipIdx}
                      {@const startSec = clipCumulativeStarts[clipIdx] ?? 0}
                      {@const endSec = startSec + clip.duration_seconds}
                      {@const isMerged = isCurrent ? visibleMergeProgressSeconds >= endSec : false}
                      {@const isMerging = isCurrent
                        ? visibleMergeProgressSeconds > startSec &&
                          visibleMergeProgressSeconds < endSec
                        : false}
                      {@const isUnmerged = isCurrent
                        ? visibleMergeProgressSeconds <= startSec
                        : true}
                      {@const ownerId = `edit-item:${item.clips?.video_assets[0]?.video_id ?? item.title}`}
                      {@const slotId = `clip:${clipIdx}:${clip.video_id}`}
                      {@const thumbnailUrl = readyImageUrl(ownerId, slotId)}

                      <!-- クリップ内進行率 -->
                      {@const clipProgressPercent = isMerging
                        ? ((visibleMergeProgressSeconds - startSec) / clip.duration_seconds) * 100
                        : 0}

                      <div
                        class="timeline-block"
                        class:active={isMerging}
                        class:unmerged={isUnmerged}
                        class:merged-right={isMerged && clipIdx < clips.length - 1}
                        class:merged-left={isCurrent
                          ? visibleMergeProgressSeconds >= startSec && clipIdx > 0
                          : false}
                        style={`flex: ${clip.duration_seconds};`}
                      >
                        <!-- 暗いモノクロ下層 (ピクセルストレッチ背景) -->
                        <div
                          class="stretch-bg-unmerged"
                          style={thumbnailUrl
                            ? `border-image-source: url('${thumbnailUrl}');`
                            : undefined}
                        ></div>
                        <!-- 暗いモノクロ下層 (中央高さ合わせ) -->
                        {#if thumbnailUrl}
                          <img
                            class="thumbnail-unmerged-fg"
                            src={thumbnailUrl}
                            alt="thumb unmerged fg"
                          />
                        {/if}

                        <!-- 明るいカラー上層 (ピクセルストレッチ背景) -->
                        <div
                          class="stretch-bg-merged"
                          style={`
                            ${thumbnailUrl ? `border-image-source: url('${thumbnailUrl}');` : ''}
                            ${
                              isMerged
                                ? 'clip-path: inset(0 0 0 0); opacity: 1;'
                                : isMerging
                                  ? `clip-path: inset(0 ${100 - clipProgressPercent}% 0 0); opacity: 1;`
                                  : 'clip-path: inset(0 100% 0 0); opacity: 0;'
                            }
                          `}
                        ></div>
                        <!-- 明るいカラー上層 (中央高さ合わせ) -->
                        {#if thumbnailUrl}
                          <img
                            class="thumbnail-merged-fg"
                            style={isMerged
                              ? 'clip-path: inset(0 0 0 0); opacity: 1;'
                              : isMerging
                                ? `clip-path: inset(0 ${100 - clipProgressPercent}% 0 0); opacity: 1;`
                                : 'clip-path: inset(0 100% 0 0); opacity: 0;'}
                            src={thumbnailUrl}
                            alt="thumb merged fg"
                          />
                        {/if}

                        <!-- WIN/LOSEカラーフレーム＆勝敗表示 -->
                        <div
                          class="block-info-overlay"
                          style={`border-bottom: 3.5px solid ${clip.judgement === 'WIN' ? 'rgb(255, 255, 20)' : 'rgb(130, 100, 255)'};`}
                        >
                          <span
                            class="block-judgement paintball-font"
                            class:judgement-win={clip.judgement === 'WIN'}
                            class:judgement-lose={clip.judgement === 'LOSE'}
                          >
                            {clip.judgement}
                          </span>
                        </div>

                        <!-- 結合完了時の光のライン演出 -->
                        {#if isCurrent && isMerged && clipIdx < clips.length - 1}
                          <div class="merge-flash-line"></div>
                        {/if}
                      </div>
                    {/each}

                    <!-- 再生ヘッド -->
                    {#if isCurrent && visibleMergeProgressSeconds > 0}
                      {@const playheadMin = Math.floor(visibleMergeProgressSeconds / 60)}
                      {@const playheadSec = Math.floor(visibleMergeProgressSeconds % 60)}
                      <div
                        class="timeline-playhead"
                        style={`left: ${currentMergingInfo.percent}%;`}
                      >
                        <div class="playhead-line"></div>
                        <div class="playhead-badge">
                          {String(playheadMin).padStart(2, '0')}:{String(playheadSec).padStart(
                            2,
                            '0'
                          )}
                        </div>
                      </div>
                    {/if}

                    <!-- 進行中の動く吹き出し (アクティブクリップの下に追従表示) -->
                    {#if isCurrent && clips[currentMergingInfo.clipIndex]}
                      {@const activeClip = clips[currentMergingInfo.clipIndex]}
                      <div
                        class="clip-bubble-popup"
                        style={`left: ${currentMergingInfo.percent}%;`}
                      >
                        <div class="bubble-content shadow-glow">
                          <div class="bubble-stage paintball-font">
                            {getStageDisplayName(activeClip.stage_name)}
                          </div>
                          <div class="bubble-stats">
                            <span class="stat-kills">{activeClip.kill}K</span>
                            <span class="stat-div">/</span>
                            <span class="stat-deaths">{activeClip.death}D</span>
                            <span class="stat-div">/</span>
                            <span class="stat-special">{activeClip.special}S</span>
                          </div>
                          {#if activeClip.gold_medals > 0 || activeClip.silver_medals > 0}
                            <div class="bubble-medals">
                              {#if activeClip.gold_medals > 0}
                                <span>🥇×{activeClip.gold_medals}</span>
                              {/if}
                              {#if activeClip.silver_medals > 0}
                                <span>🥈×{activeClip.silver_medals}</span>
                              {/if}
                            </div>
                          {/if}
                        </div>
                        <div class="bubble-arrow"></div>
                      </div>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      </section>

      <!-- 2. 右側：アップロード待機エリア -->
      <section
        class="wf-panel platform-panel"
        class:responsive-stage-active={responsiveStage === 'waiting'}
        aria-label="2. 待機"
        aria-current={responsiveStage === 'waiting' ? 'step' : undefined}
      >
        <div class="panel-header">
          <div class="panel-title-group">
            <div
              class="pipeline-stage-icon waiting-stage-icon"
              role="img"
              aria-label="待機中エリア"
            >
              <SquareStack size={18} />
            </div>
            <h3 class="stage-title" aria-label="2. 待機">
              <span class="stage-number">2.</span>
              <span class="stage-name">待機</span>
            </h3>
          </div>
        </div>

        <div class="platform-container glass-surface">
          {#if completedVideos.length === 0}
            <div class="platform-empty-slot">
              <UploadCloud size={36} class="muted-icon" />
              <p>編集完了した動画がここに蓄積されます</p>
            </div>
          {:else}
            <div class="waiting-videos-list">
              {#each completedVideos as video (video.id)}
                {@const videoImage = completedVideoImage(video)}
                <!-- アニメーション付き追加用の receive をバインド -->
                <div
                  class="waiting-video-card"
                  class:transfer-active={isActiveUploadVideo(video)}
                  animate:flip={{ duration: 520 }}
                  in:receive={{ key: video.id }}
                >
                  <div
                    class="waiting-card-thumb"
                    class:transfer-source={isActiveUploadVideo(video)}
                  >
                    {#if videoImage}
                      <img src={videoImage} alt="thumb" />
                    {/if}
                    {#if isActiveUploadVideo(video)}
                      <div class="upload-source-grid" aria-hidden="true">
                        {#each uploadBlockIndexes as blockIndex}
                          <span
                            class="upload-tile source-tile"
                            class:transferred={isUploadBlockTransferredFromSource(blockIndex)}
                            style={thumbnailBlockStyle(videoImage, blockIndex)}
                          ></span>
                        {/each}
                      </div>
                    {/if}
                    <div class="waiting-card-date paintball-font">{video.dateLabel}</div>
                  </div>
                  <div class="waiting-card-details">
                    <h4 class="waiting-card-title paintball-font">{video.title}</h4>
                    <span class="waiting-status-badge">編集完了・アップロード待ち</span>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </section>

      <!-- 3. 右端：YouTube 受信・再構成エリア -->
      <section
        class="wf-panel youtube-panel"
        class:expanded={uploadStageExpanded}
        class:responsive-stage-active={responsiveStage === 'uploading'}
        aria-label="3. アップロード"
        aria-current={responsiveStage === 'uploading' ? 'step' : undefined}
      >
        <div class="panel-header stage-panel-header youtube-header">
          <div class="panel-title-group">
            <div
              class="pipeline-stage-icon youtube-stage-icon"
              role="img"
              aria-label="アップロードエリア"
            >
              <Youtube size={18} />
            </div>
            <h3 class="stage-title" aria-label="3. アップロード">
              <span class="stage-number">3.</span>
              <span class="stage-name">アップロード</span>
            </h3>
          </div>
        </div>

        <div class="youtube-stage-region" role="region" aria-label={youtubeAreaLabel}>
          {#if uploadTask?.status === 'failed'}
            <div class="youtube-terminal-status failed" role="alert" aria-label="アップロード失敗">
              <AlertTriangle size={44} aria-hidden="true" />
              <strong>アップロードに失敗しました</strong>
              <p>{uploadTask.errorMessage ?? '処理に失敗しました。'}</p>
            </div>
          {:else if uploadTask?.status === 'succeeded'}
            <div
              class="youtube-terminal-status succeeded"
              role="status"
              aria-label="アップロード完了"
            >
              <Youtube size={44} aria-hidden="true" />
              <strong>アップロードが完了しました</strong>
              <p>{uploadTask.successMessage ?? 'アップロードが完了しました。'}</p>
            </div>
          {:else if uploadStageExpanded}
            <div class="youtube-receiver-wrap">
              {#if uploadTask?.status === 'running' && activeUploadVideo && flyingUploadBlocks.length > 0}
                <div
                  class="youtube-flying-blocks"
                  role="img"
                  aria-label="YouTubeへ飛行中のサムネイルブロック"
                >
                  {#each flyingUploadBlocks as block (block.key)}
                    <span
                      class="flying-upload-tile"
                      data-testid="flying-upload-tile"
                      style={flyingBlockStyle(
                        completedVideoImage(activeUploadVideo),
                        block.blockIndex,
                        block.flightIndex
                      )}
                    ></span>
                  {/each}
                </div>
              {/if}

              <div
                class="youtube-receiver glass-surface"
                role="progressbar"
                aria-label="YouTube再構成進捗"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={uploadReceiverBlockCount}
              >
                <div class="youtube-brand-mark" aria-hidden="true">
                  <Youtube size={30} />
                </div>

                {#if activeUploadVideo}
                  <div class="upload-receiver-grid" aria-label="YouTube側で再構成中のサムネイル">
                    {#each uploadBlockIndexes as blockIndex}
                      <span
                        class="upload-tile receiver-tile"
                        class:received={isUploadBlockReceived(blockIndex)}
                        style={thumbnailBlockStyle(
                          completedVideoImage(activeUploadVideo),
                          blockIndex
                        )}
                      ></span>
                    {/each}
                  </div>
                {:else}
                  <div class="youtube-receiver-empty" aria-hidden="true">
                    <Youtube size={44} />
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </section>
    </main>
  </section>

  {#snippet footer()}
    <footer class="dialog-footer">
      <!-- スリープトグル -->
      <div class="footer-option">
        <label class="sleep-toggle" class:disabled={sleepToggleDisabled}>
          <input
            type="checkbox"
            checked={sleepAfterUploadEnabled}
            disabled={sleepToggleDisabled}
            aria-label="完了後スリープ"
            onchange={handleSleepAfterUploadChange}
          />
          <span class="toggle-slider"></span>
          <span class="toggle-label">完了後スリープ</span>
        </label>
        {#if optionErrorMessage}
          <span class="option-error" role="alert">{optionErrorMessage}</span>
        {/if}
      </div>

      <div class="footer-actions">
        <!-- キャンセルボタンの追加 -->
        {#if anyRunning}
          <button
            type="button"
            class="action-button cancel-btn"
            onclick={handleCancelProcess}
            disabled={cancelLoading}
          >
            {#if cancelLoading}中断中...{:else}編集をキャンセル{/if}
          </button>
        {/if}
        <button
          type="button"
          class="action-button primary"
          onclick={handleClose}
          disabled={closeDisabled}
          title={closeDisabled ? '処理中は閉じることができません' : ''}
        >
          閉じる
        </button>
      </div>
    </footer>
  {/snippet}
</BaseDialog>

<style>
  .paintball-font {
    font-family: var(--theme-font-heading, 'Outfit', sans-serif);
  }

  /* ====== アクセシビリティ ====== */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  /* ====== レイアウト ====== */
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  /* ====== ミニ警告バナー ====== */
  .connection-mini-alert {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.75rem;
    background: rgba(255, 95, 136, 0.12);
    border: 1px solid rgba(255, 95, 136, 0.25);
    color: #ff5f88;
    font-size: 0.78rem;
    border-radius: 6px;
    font-weight: 500;
  }

  .mini-retry-btn {
    margin-left: auto;
    background: transparent;
    border: 1px solid rgba(255, 95, 136, 0.4);
    color: #ff5f88;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.72rem;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .mini-retry-btn:hover {
    background: rgba(255, 95, 136, 0.15);
  }

  /* ====== パイプライン ====== */
  .wf-pipeline {
    display: flex;
    flex-direction: row;
    padding: 0.15rem 0;
    gap: 0.75rem;
    min-height: 0;
    flex: 1 1 auto;
    overflow: hidden;
  }

  .wf-pipeline.upload-stage-expanded {
    gap: 0.85rem;
  }

  .wf-panel {
    position: relative;
    display: flex;
    flex-direction: column;
    background: rgba(14, 16, 32, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 0.75rem;
    min-height: 0;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    transition:
      width 0.7s cubic-bezier(0.22, 1, 0.36, 1),
      flex-basis 0.7s cubic-bezier(0.22, 1, 0.36, 1),
      padding 0.7s cubic-bezier(0.22, 1, 0.36, 1),
      opacity 0.35s ease;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
    flex-shrink: 0;
  }

  .stage-panel-header {
    justify-content: flex-start;
  }

  .panel-header h3 {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
    letter-spacing: 0.05em;
  }

  .panel-title-group {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
  }

  .stage-title {
    display: inline-flex;
    align-items: baseline;
    gap: 0.25rem;
    min-width: 0;
    white-space: nowrap;
  }

  .stage-number {
    color: rgba(var(--theme-rgb-accent), 0.9);
    font-variant-numeric: tabular-nums;
  }

  .stage-name {
    min-width: 0;
  }

  .pipeline-stage-icon {
    color: rgba(var(--theme-rgb-accent), 0.86);
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 999px;
    background: rgba(var(--theme-rgb-accent), 0.1);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.24);
    box-shadow: 0 0 16px rgba(var(--theme-rgb-accent), 0.12);
    flex-shrink: 0;
  }

  .editing-stage-icon {
    opacity: 0.82;
    pointer-events: none;
  }

  .waiting-stage-icon {
    width: 28px;
    height: 28px;
  }

  .youtube-stage-icon {
    color: rgba(var(--theme-rgb-danger), 0.85);
    background: rgba(var(--theme-rgb-danger), 0.1);
    border-color: rgba(var(--theme-rgb-danger), 0.24);
    box-shadow: 0 0 16px rgba(var(--theme-rgb-danger), 0.12);
  }

  /* --- 1. 中央: Video Assembly --- */
  .assembly-panel {
    flex: 1 1 auto;
    min-width: 0;
  }

  .wf-pipeline.upload-stage-expanded .assembly-panel {
    flex: 0 0 40px;
    width: 40px;
    align-items: center;
    justify-content: center;
    padding: 0.65rem 0.45rem;
    overflow: visible;
  }

  .wf-pipeline.upload-stage-expanded .assembly-panel .editing-stage-icon {
    position: static;
    width: 34px;
    height: 34px;
    opacity: 0.72;
  }

  .wf-pipeline.upload-stage-expanded .assembly-panel .stage-panel-header {
    margin-bottom: 0;
  }

  .wf-pipeline.upload-stage-expanded .assembly-panel .panel-title-group {
    flex-direction: column;
    gap: 0.25rem;
  }

  .wf-pipeline.upload-stage-expanded .assembly-panel .stage-title {
    flex-direction: column;
    align-items: center;
    gap: 0;
    font-size: 0.58rem;
    line-height: 1.05;
    text-align: center;
    white-space: normal;
  }

  .wf-pipeline.upload-stage-expanded .assembly-monitor {
    display: none;
  }

  .assembly-monitor {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 0.75rem;
    gap: 0.5rem;
    min-height: 0;
    border-radius: 8px;
    background: rgba(6, 8, 15, 0.4);
  }

  .video-preview-window {
    width: 100%;
    aspect-ratio: 16 / 9;
    position: relative;
    background: #000;
    background-position: center;
    background-size: cover;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.03);
    flex-shrink: 0;
  }

  .video-preview-window.has-preview-backdrop::before {
    content: '';
    position: absolute;
    inset: 0;
    background: inherit;
    background-position: center;
    background-size: cover;
    opacity: 0.9;
  }

  .preview-bg {
    width: 100%;
    height: 100%;
    object-fit: cover;
    position: absolute;
    inset: 0;
    z-index: 1;
  }

  .preview-container {
    width: 100%;
    height: 100%;
    position: relative;
  }

  .preview-animation-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
    background-position: center;
    background-size: cover;
    --pixel-reveal-progress: 1;
    --pixel-reveal-complete-height: 100%;
    --pixel-reveal-current-row-top: 100%;
    --pixel-reveal-current-width: 100%;
    --pixel-reveal-row-height: 1px;
  }

  .preview-animation-wrapper .preview-bg {
    position: absolute;
    inset: 0;
  }

  .preview-final {
    opacity: 1;
    filter: none;
    -webkit-mask-image: linear-gradient(#000 0 0), linear-gradient(#000 0 0);
    mask-image: linear-gradient(#000 0 0), linear-gradient(#000 0 0);
    -webkit-mask-position:
      0 0,
      0 var(--pixel-reveal-current-row-top);
    mask-position:
      0 0,
      0 var(--pixel-reveal-current-row-top);
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-size:
      100% var(--pixel-reveal-complete-height),
      var(--pixel-reveal-current-width) var(--pixel-reveal-row-height);
    mask-size:
      100% var(--pixel-reveal-complete-height),
      var(--pixel-reveal-current-width) var(--pixel-reveal-row-height);
    will-change:
      mask-size,
      -webkit-mask-size,
      mask-position,
      -webkit-mask-position;
  }

  .preview-animation-wrapper.final-settled .preview-final {
    animation: final-thumbnail-lock 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  @keyframes final-thumbnail-lock {
    0% {
      transform: scale(1.01);
    }
    65% {
      transform: scale(0.998);
    }
    100% {
      transform: scale(1);
    }
  }

  .video-preview-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    color: rgba(255, 255, 255, 0.28);
    font-size: 0.85rem;
  }

  .video-preview-empty :global(.muted-icon),
  .platform-empty-slot :global(.muted-icon) {
    stroke-width: 1.25;
    margin-bottom: 0.5rem;
    opacity: 0.5;
  }

  /* マッチ・ルール表示（動画枠外・直上・左揃え） */
  .common-metadata-overlay {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    font-weight: 800;
    color: rgba(255, 255, 255, 0.55);
    padding-left: 0.25rem;
    margin-bottom: 2px;
    align-self: flex-start;
  }

  .common-metadata-overlay .meta-value {
    color: #2ff6e3;
    text-shadow: 0 0 6px rgba(47, 246, 227, 0.4);
  }

  .common-metadata-overlay .meta-separator {
    color: rgba(255, 255, 255, 0.15);
    margin: 0 0.25rem;
  }

  /* --- マルチシークバーエリア --- */
  .multi-timeline-area {
    flex: 1;
    overflow: visible;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding-right: 0.25rem;
    position: relative;
    z-index: 10;
    padding-top: 8px; /* 余白を最小化し、動画枠に近づける */
  }

  .empty-timeline-placeholder {
    display: grid;
    place-items: center;
    height: 100px;
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    color: rgba(255, 255, 255, 0.25);
    font-size: 0.85rem;
  }

  .timeline-row {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0.5rem;
    min-height: 70px;
    position: relative;
    z-index: 10;
  }

  .timeline-row.active {
    z-index: 40; /* 吹き出しが動画枠等の下に隠れないようにする */
    margin-bottom: 3.25rem;
  }

  /* 上部の日時ラベル */
  .timeline-date-header {
    font-size: 0.82rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.45);
    margin-bottom: 2px;
    transition: color 0.3s ease;
    text-align: left;
  }

  .timeline-date-header.active {
    color: #2ff6e3;
    text-shadow: 0 0 6px rgba(47, 246, 227, 0.3);
  }

  /* シークバーコンテナ */
  .timeline-track-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    position: relative;
    padding-top: 1.15rem; /* レートタグ表示用の隙間をシークバーのすぐ上に確保 */
  }

  .timeline-track {
    height: 48px;
    background: rgba(0, 0, 0, 0.55);
    border-radius: 8px;
    border: 1.5px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    padding: 2px;
    gap: 0;
    position: relative;
    z-index: 10;
    transition:
      border-color 0.3s ease,
      background-color 0.3s ease;
  }

  .timeline-track.inactive {
    border-color: rgba(255, 255, 255, 0.03);
    background: rgba(0, 0, 0, 0.3);
    pointer-events: none;
  }

  .timeline-row.active .timeline-track {
    border-color: rgba(255, 255, 255, 0.15);
  }

  /* クリップブロック */
  .timeline-block {
    height: 100%;
    position: relative;
    border-radius: 5px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 2.5px;
    transition:
      background 0.3s ease,
      border-color 0.3s ease,
      opacity 0.3s ease,
      margin-right 0.35s cubic-bezier(0.25, 1.4, 0.5, 1),
      border-radius 0.3s ease;
  }

  .timeline-block:last-child {
    margin-right: 0;
  }

  /* 結合された境界のスタイリング（マージンと角丸を削って密着） */
  .timeline-block.merged-right {
    margin-right: 0;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right-width: 0; /* ボーダー幅をなくして1pxの隙間を完全に詰める */
  }

  .timeline-block.merged-left {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left-width: 0; /* ボーダー幅をなくして1pxの隙間を完全に詰める */
  }

  /* 結合完了時の光のライン演出 */
  .merge-flash-line {
    position: absolute;
    right: -2px; /* 隙間を詰めたため位置を -2px に調整 */
    top: -4px;
    bottom: -4px;
    width: 4px; /* 太くして目立たせる */
    background: #fff;
    box-shadow:
      0 0 10px #fff,
      0 0 20px #2ff6e3,
      0 0 35px #2ff6e3,
      0 0 50px #01f9c4; /* グロー効果を大幅強化 */
    z-index: 30;
    pointer-events: none;
    animation: flash-impact 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }

  /* 左右に広がるウェーブ（衝撃波）エフェクト */
  .merge-flash-line::before {
    content: '';
    position: absolute;
    inset: 0;
    background: inherit;
    box-shadow: inherit;
    border-radius: 50%;
    animation: flash-wave 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }

  @keyframes flash-impact {
    0% {
      opacity: 1;
      transform: scaleY(0) scaleX(3);
    }
    15% {
      opacity: 1;
      transform: scaleY(1.2) scaleX(2.5);
      filter: brightness(2);
    }
    40% {
      opacity: 0.8;
      transform: scaleY(1) scaleX(1);
    }
    100% {
      opacity: 0;
      transform: scaleY(1) scaleX(0.2);
      background: #2ff6e3;
    }
  }

  @keyframes flash-wave {
    0% {
      transform: scale(1);
      opacity: 1;
    }
    100% {
      transform: scaleX(8) scaleY(1.5);
      opacity: 0;
    }
  }

  .timeline-block img {
    pointer-events: none;
  }

  /* 背景ピクセルストレッチ共通 */
  .stretch-bg-unmerged,
  .stretch-bg-merged {
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-style: solid;
    border-width: 0 46% 0 46%; /* 左右のボーダー領域を広く取る */
    border-image-slice: 0 8% 0 8% fill; /* 画像の左右端 8% を 46% の領域に引き伸ばす */
    border-image-repeat: stretch;
  }

  /* 前面中央高さ合わせ共通 */
  .thumbnail-unmerged-fg,
  .thumbnail-merged-fg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    z-index: 2; /* ストレッチ背景より手前に配置 */
    pointer-events: none;
  }

  /* モノクロ・暗め（未進行） */
  .timeline-block.unmerged .stretch-bg-merged,
  .timeline-block.unmerged .thumbnail-merged-fg {
    opacity: 0 !important;
  }

  .timeline-block .stretch-bg-unmerged {
    filter: grayscale(1) brightness(0.4) blur(2px);
    opacity: 0.55;
  }

  .timeline-block .thumbnail-unmerged-fg {
    filter: grayscale(1) brightness(0.4);
    opacity: 0.55;
  }

  /* フルカラー・はっきり（進行済み） */
  .timeline-block .stretch-bg-merged {
    filter: blur(2px);
    opacity: 1;
    transition:
      clip-path 0.5s ease-out,
      opacity 0.5s ease-out;
  }

  .timeline-block .thumbnail-merged-fg {
    filter: none;
    opacity: 1;
    transition:
      clip-path 0.5s ease-out,
      opacity 0.5s ease-out;
  }

  .block-info-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.15rem 0.3rem;
    z-index: 5;
    pointer-events: none;
  }

  .block-judgement {
    font-size: 0.95rem;
    font-weight: 800;
    margin: auto;
    text-align: center;
    width: 100%;
    text-shadow:
      -1.5px -1.5px 0 #000,
      1.5px -1.5px 0 #000,
      -1.5px 1.5px 0 #000,
      1.5px 1.5px 0 #000,
      0 0 4px rgba(0, 0, 0, 0.8);
  }

  .block-judgement.judgement-win {
    color: #ffff14; /* WIN: 黄色 */
  }

  .block-judgement.judgement-lose {
    color: #8264ff; /* LOSE: 青紫 */
  }

  /* 再生ヘッド */
  .timeline-playhead {
    position: absolute;
    top: -2px;
    bottom: -2px;
    width: 2px;
    background: #2ff6e3;
    box-shadow: 0 0 10px #2ff6e3;
    pointer-events: none;
    transform: translateX(-50%);
    z-index: 20;
    transition: left 0.5s ease-out;
  }

  .playhead-line {
    width: 100%;
    height: 100%;
  }

  .playhead-badge {
    position: absolute;
    top: -16px;
    left: 50%;
    transform: translateX(-50%);
    background: #2ff6e3;
    color: #06080f;
    font-size: 0.55rem;
    font-weight: 800;
    padding: 0px 4px;
    border-radius: 2px;
    white-space: nowrap;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
  }

  /* レートピン留めタグ (シークバーのすぐ上) */
  .timeline-rate-tag {
    position: absolute;
    top: 0;
    height: 1rem;
    pointer-events: none;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding-left: 6px;
    font-size: 0.68rem;
    font-weight: 800;
    color: #ffffff;
    text-shadow:
      0 1px 3px rgba(0, 0, 0, 0.9),
      0 0 2px #000;
    border-left: 2px solid rgba(255, 95, 136, 0.95);
    box-shadow: -1px 0 3px rgba(255, 95, 136, 0.3);
    z-index: 5;
  }

  .timeline-rate-tag.rate-x {
    color: #01f9c4;
    border-left-color: #01f9c4;
    box-shadow: -1px 0 3px rgba(1, 249, 196, 0.3);
  }

  .timeline-rate-tag.rate-bankara {
    color: #fa6100;
    border-left-color: #fa6100;
    box-shadow: -1px 0 3px rgba(250, 97, 0, 0.3);
  }

  .timeline-rate-tag.rate-event {
    color: #f12e7d;
    border-left-color: #f12e7d;
    box-shadow: -1px 0 3px rgba(241, 46, 125, 0.3);
  }

  /* 進行中クリップへの追従吹き出し */
  .clip-bubble-popup {
    position: absolute;
    top: calc(100% + 8px);
    transform: translateX(-50%);
    z-index: 100; /* 背面に隠れないように前面へ配置 */
    display: flex;
    flex-direction: column;
    align-items: center;
    pointer-events: none;
    animation: popup-bounce 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    transition: left 0.5s ease-out;
  }

  @keyframes popup-bounce {
    0% {
      transform: translateX(-50%) scale(0.6) translateY(10px);
      opacity: 0;
    }
    100% {
      transform: translateX(-50%) scale(1) translateY(0);
      opacity: 1;
    }
  }

  .bubble-content {
    background: rgba(10, 12, 28, 0.9);
    border: 2px solid #2ff6e3;
    box-shadow: 0 4px 16px rgba(47, 246, 227, 0.35);
    border-radius: 6px;
    padding: 0.35rem 0.6rem;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    align-items: center;
    min-width: 90px;
    width: max-content;
    white-space: nowrap;
  }

  .bubble-stage {
    font-size: 0.68rem;
    font-weight: 700;
    color: #2ff6e3;
    text-align: center;
  }

  .bubble-stats {
    display: flex;
    align-items: center;
    gap: 0.2rem;
    font-size: 0.62rem;
    font-weight: 600;
    color: #f5f5ff;
  }

  .stat-div {
    color: rgba(255, 255, 255, 0.3);
  }

  .bubble-medals {
    display: flex;
    gap: 0.1rem;
    font-size: 0.62rem;
    margin-top: 1px;
  }

  .bubble-arrow {
    order: -1;
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-bottom: 6px solid #2ff6e3;
    margin-bottom: -1px;
  }

  /* --- 2. 右側: Upload Waiting Area --- */
  .platform-panel {
    width: 300px;
    flex-shrink: 0;
  }

  .wf-pipeline.upload-stage-expanded .platform-panel {
    width: clamp(300px, 30vw, 460px);
    flex: 1 1 300px;
    min-width: 280px;
  }

  .platform-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 0.75rem;
    background: rgba(6, 8, 15, 0.35);
    border-radius: 8px;
    min-height: 0;
    overflow-y: auto;
  }

  .platform-empty-slot {
    flex: 1;
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: rgba(255, 255, 255, 0.25);
    font-size: 0.75rem;
    padding: 2rem 1rem;
    gap: 0.5rem;
  }

  .waiting-videos-list {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  .waiting-video-card {
    background: rgba(14, 16, 32, 0.75);
    border: 1.5px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 0.45rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    transition: border-color 0.2s ease;
  }

  .waiting-video-card:hover {
    border-color: rgba(47, 246, 227, 0.25);
  }

  .waiting-video-card.transfer-active {
    border-color: rgba(var(--theme-rgb-accent), 0.45);
    box-shadow:
      inset 0 0 18px rgba(var(--theme-rgb-accent), 0.08),
      0 0 18px rgba(var(--theme-rgb-accent), 0.12);
  }

  .waiting-card-thumb {
    position: relative;
    aspect-ratio: 16 / 9;
    border-radius: 5px;
    overflow: hidden;
    background: #000;
  }

  .waiting-card-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: opacity 0.25s ease;
  }

  .waiting-card-thumb.transfer-source > img {
    opacity: 0;
  }

  .upload-source-grid,
  .upload-receiver-grid {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    grid-template-rows: repeat(10, 1fr);
    gap: 1px;
    background: rgba(var(--theme-rgb-black), 0.42);
  }

  .upload-tile {
    background-repeat: no-repeat;
    min-width: 0;
    min-height: 0;
    transition:
      opacity 0.45s cubic-bezier(0.22, 1, 0.36, 1),
      transform 0.45s cubic-bezier(0.22, 1, 0.36, 1),
      filter 0.45s ease;
  }

  .source-tile {
    opacity: 1;
    transform: scale(1);
  }

  .source-tile.transferred {
    opacity: 0.08;
    transform: scale(0.72);
    filter: saturate(0.2) brightness(0.5);
  }

  .receiver-tile {
    opacity: 0.04;
    transform: scale(0.52);
    filter: saturate(0.3) brightness(0.55);
  }

  .receiver-tile.received {
    opacity: 1;
    transform: scale(1);
    filter: saturate(1.1) brightness(1.08);
  }

  .waiting-card-date {
    position: absolute;
    top: 4px;
    left: 4px;
    font-size: 0.58rem;
    font-weight: 700;
    color: #fff;
    background: rgba(0, 0, 0, 0.65);
    padding: 1px 4px;
    border-radius: 2px;
  }

  .waiting-card-details {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .waiting-card-title {
    margin: 0;
    font-size: 0.75rem;
    font-weight: 700;
    color: #fff;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .waiting-status-badge {
    font-size: 0.58rem;
    color: #2ff6e3;
    font-weight: 600;
  }

  /* --- 3. 右端: YouTube Receiving Area --- */
  .youtube-panel {
    position: relative;
    width: 64px;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    padding: 0.65rem 0.45rem;
    overflow: visible;
    border-color: rgba(var(--theme-rgb-danger), 0.16);
  }

  .youtube-panel .stage-number {
    color: rgba(var(--theme-rgb-danger), 0.9);
  }

  .youtube-panel.expanded {
    width: clamp(340px, 34vw, 560px);
    flex: 1.15 1 340px;
    min-width: 320px;
    align-items: stretch;
    justify-content: flex-start;
    padding: 0.75rem;
    border-color: rgba(var(--theme-rgb-danger), 0.32);
    box-shadow:
      inset 0 0 22px rgba(var(--theme-rgb-danger), 0.07),
      0 0 22px rgba(var(--theme-rgb-danger), 0.12);
  }

  .youtube-panel:not(.expanded) .stage-panel-header {
    margin-bottom: 0;
  }

  .youtube-panel:not(.expanded) .panel-title-group {
    flex-direction: column;
    gap: 0.35rem;
  }

  .youtube-panel:not(.expanded) .stage-title {
    flex-direction: column;
    align-items: center;
    gap: 0;
    font-size: 0.56rem;
    line-height: 1.05;
    text-align: center;
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .youtube-terminal-status {
    display: flex;
    flex: 1;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    min-height: 12rem;
    padding: 1rem;
    border: 1px solid transparent;
    border-radius: 0.75rem;
    text-align: center;
  }

  .youtube-terminal-status strong {
    font-size: 1rem;
  }

  .youtube-terminal-status p {
    margin: 0;
    color: rgba(var(--theme-rgb-white), 0.78);
    overflow-wrap: anywhere;
  }

  .youtube-terminal-status.succeeded {
    color: var(--theme-accent-color);
    border-color: rgba(var(--theme-rgb-accent), 0.28);
    background: rgba(var(--theme-rgb-accent), 0.06);
  }

  .youtube-terminal-status.failed {
    color: var(--theme-status-danger);
    border-color: rgba(var(--theme-rgb-danger), 0.32);
    background: rgba(var(--theme-rgb-danger), 0.08);
  }

  .youtube-receiver-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .youtube-receiver {
    position: relative;
    width: 100%;
    max-width: 100%;
    aspect-ratio: 16 / 9;
    border-radius: 10px;
    overflow: hidden;
    background:
      radial-gradient(circle at center, rgba(var(--theme-rgb-danger), 0.18), transparent 62%),
      rgba(var(--theme-rgb-black), 0.35);
    border: 1px solid rgba(var(--theme-rgb-danger), 0.28);
    box-shadow:
      inset 0 0 24px rgba(var(--theme-rgb-danger), 0.08),
      0 0 18px rgba(var(--theme-rgb-danger), 0.1);
  }

  .youtube-brand-mark {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    color: rgba(var(--theme-rgb-danger), 0.18);
    pointer-events: none;
    z-index: 0;
  }

  .upload-receiver-grid {
    z-index: 1;
  }

  .youtube-receiver-empty {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    color: rgba(var(--theme-rgb-danger), 0.22);
  }

  .youtube-flying-blocks {
    position: absolute;
    left: -4.8rem;
    top: 50%;
    width: 13rem;
    height: 6rem;
    transform: translateY(-50%);
    pointer-events: none;
    z-index: 4;
    overflow: visible;
  }

  .flying-upload-tile {
    position: absolute;
    left: 0;
    top: calc(50% + var(--flight-y));
    width: 1.32rem;
    height: 0.84rem;
    border-radius: 2px;
    border: 1px solid rgba(var(--theme-rgb-white), 0.18);
    background-repeat: no-repeat;
    box-shadow:
      0 0 10px rgba(var(--theme-rgb-accent), 0.42),
      0 0 18px rgba(var(--theme-rgb-danger), 0.18);
    opacity: 0;
    animation: thumbnail-block-flight 1.22s cubic-bezier(0.22, 1, 0.36, 1) both;
    animation-delay: var(--flight-delay);
    will-change: transform, opacity;
  }

  @keyframes thumbnail-block-flight {
    0% {
      opacity: 0;
      transform: translate3d(-2.8rem, var(--flight-start-y), 0) scale(0.58)
        rotate(var(--flight-rotate-start));
    }
    14% {
      opacity: 1;
    }
    52% {
      opacity: 1;
      transform: translate3d(4.4rem, var(--flight-arc), 0) scale(0.92) rotate(0deg);
    }
    82% {
      opacity: 0.9;
    }
    100% {
      opacity: 0;
      transform: translate3d(11.4rem, 0, 0) scale(1.02) rotate(var(--flight-rotate));
    }
  }

  /* ====== グラスモーフィズム ====== */
  .glass-surface {
    background: rgba(14, 16, 32, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow: inset 0 0 16px rgba(255, 255, 255, 0.02);
  }

  .shadow-glow {
    box-shadow:
      0 4px 16px rgba(0, 0, 0, 0.5),
      0 0 8px rgba(47, 246, 227, 0.15);
  }

  /* ====== フッター ====== */
  .dialog-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 1.25rem;
  }

  .footer-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .sleep-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    flex-shrink: 0;
  }

  .sleep-toggle.disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .sleep-toggle input[type='checkbox'] {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .sleep-toggle .toggle-slider {
    position: relative;
    display: inline-block;
    width: 2.4rem;
    height: 1.3rem;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 1rem;
    transition: all 0.25s ease;
    flex-shrink: 0;
  }

  .sleep-toggle .toggle-slider::before {
    content: '';
    position: absolute;
    width: 0.9rem;
    height: 0.9rem;
    left: 0.2rem;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(255, 255, 255, 0.8);
    border-radius: 50%;
    transition: all 0.25s ease;
  }

  .sleep-toggle input:checked + .toggle-slider {
    background: rgba(47, 246, 227, 0.6);
    border-color: rgba(47, 246, 227, 0.4);
  }

  .sleep-toggle input:checked + .toggle-slider::before {
    left: calc(100% - 1.1rem);
    background: #fff;
  }

  .toggle-label {
    font-size: 0.78rem;
    color: rgba(255, 255, 255, 0.5);
    white-space: nowrap;
  }

  .option-error {
    font-size: 0.75rem;
    color: #ff5f88;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .footer-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .action-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 1.1rem;
    border-radius: 0.5rem;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 0.85);
    background: rgba(255, 255, 255, 0.05);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .action-button:hover:not(:disabled) {
    border-color: rgba(255, 255, 255, 0.35);
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
  }

  .action-button.primary {
    border-color: rgba(47, 246, 227, 0.3);
    color: #2ff6e3;
    background: rgba(47, 246, 227, 0.05);
  }

  .action-button.primary:hover:not(:disabled) {
    border-color: #2ff6e3;
    color: #06080f;
    background: #2ff6e3;
    box-shadow: 0 0 10px rgba(47, 246, 227, 0.3);
  }

  .action-button.cancel-btn {
    border-color: rgba(255, 95, 136, 0.3);
    color: #ff5f88;
    background: rgba(255, 95, 136, 0.05);
  }

  .action-button.cancel-btn:hover:not(:disabled) {
    border-color: #ff5f88;
    color: #fff;
    background: #ff5f88;
    box-shadow: 0 0 10px rgba(255, 95, 136, 0.3);
  }

  .action-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* 切り替え時の一時的な transition 無効化 */
  .no-transition,
  .no-transition :global(*) {
    transition: none !important;
  }
  .youtube-stage-region {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 0;
  }

  @media (max-width: 56.25rem) {
    .dialog-body {
      padding: 0.5rem 0.75rem;
      overflow-x: hidden;
      overflow-y: auto;
      overscroll-behavior: contain;
    }

    .wf-pipeline,
    .wf-pipeline.upload-stage-expanded {
      flex: 0 0 auto;
      flex-direction: column;
      gap: 0.5rem;
      overflow: visible;
    }

    .wf-panel,
    .wf-pipeline.upload-stage-expanded .assembly-panel,
    .wf-pipeline.upload-stage-expanded .platform-panel,
    .youtube-panel,
    .youtube-panel.expanded {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      flex: 0 0 auto;
      align-items: stretch;
      justify-content: flex-start;
      padding: 0.625rem 0.75rem;
      overflow: hidden;
      transition: opacity 0.35s ease;
    }

    .wf-panel.responsive-stage-active {
      min-height: clamp(18rem, calc(100dvh - 13rem), 34rem);
    }

    .wf-panel:not(.responsive-stage-active) {
      height: 2.75rem;
      min-height: 2.75rem;
      padding: 0.45rem 0.65rem;
    }

    .wf-panel:not(.responsive-stage-active) > :not(.panel-header):not(.youtube-stage-region) {
      display: none;
    }

    .wf-panel:not(.responsive-stage-active) .youtube-stage-region {
      flex: 0 0 0;
      height: 0;
      min-height: 0;
      overflow: hidden;
    }

    .wf-panel:not(.responsive-stage-active) .youtube-stage-region > * {
      display: none;
    }

    .wf-panel:not(.responsive-stage-active) .panel-header,
    .wf-pipeline.upload-stage-expanded .assembly-panel .stage-panel-header,
    .youtube-panel:not(.expanded) .stage-panel-header {
      margin-bottom: 0;
    }

    .wf-pipeline.upload-stage-expanded .assembly-panel .panel-title-group,
    .youtube-panel:not(.expanded) .panel-title-group {
      flex-direction: row;
      gap: 0.45rem;
    }

    .wf-pipeline.upload-stage-expanded .assembly-panel .stage-title,
    .youtube-panel:not(.expanded) .stage-title {
      flex-direction: row;
      align-items: baseline;
      gap: 0.25rem;
      font-size: 0.85rem;
      line-height: 1.2;
      text-align: left;
      white-space: nowrap;
    }

    .wf-panel:not(.responsive-stage-active) .pipeline-stage-icon,
    .wf-pipeline.upload-stage-expanded .assembly-panel .editing-stage-icon {
      position: static;
      width: 1.75rem;
      height: 1.75rem;
    }

    .wf-pipeline.upload-stage-expanded .assembly-panel.responsive-stage-active .assembly-monitor {
      display: flex;
    }

    .youtube-flying-blocks {
      display: none;
    }

    .assembly-panel.responsive-stage-active .timeline-row:not(.active) {
      display: none;
    }
  }

  @media (min-width: 40.0625rem) and (max-width: 56.25rem) and (min-height: 40rem) {
    .assembly-panel.responsive-stage-active {
      height: clamp(24rem, calc(100dvh - 17rem), 34rem);
      min-height: 0;
    }

    .assembly-panel.responsive-stage-active .assembly-monitor {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 0.375rem;
      padding: 0.5rem;
      overflow: hidden;
    }

    .assembly-panel.responsive-stage-active .video-preview-window {
      width: auto;
      height: 100%;
      min-width: 0;
      min-height: 0;
      max-width: 100%;
      max-height: 100%;
      align-self: center;
      justify-self: center;
    }

    .assembly-panel.responsive-stage-active .multi-timeline-area {
      flex: none;
      gap: 0;
      padding-top: 0.25rem;
      padding-right: 0;
    }

    .dialog-footer {
      padding-block: 0;
    }
  }

  @media (max-width: 40rem) {
    .dialog-body {
      gap: 0.375rem;
      padding: 0.5rem;
      -webkit-overflow-scrolling: touch;
    }

    .wf-panel.responsive-stage-active {
      min-height: clamp(17rem, calc(100dvh - 12.5rem), 30rem);
    }

    .connection-mini-alert {
      flex-wrap: wrap;
      padding: 0.5rem 0.625rem;
    }

    .connection-mini-alert span {
      flex: 1 1 12rem;
      min-width: 0;
    }

    .mini-retry-btn {
      min-height: 2.75rem;
      margin-left: 0;
      padding-inline: 0.75rem;
    }

    .dialog-footer {
      flex-direction: column;
      align-items: stretch;
      gap: 0.5rem;
      padding: 0.625rem 0.75rem;
    }

    .footer-option,
    .footer-actions {
      width: 100%;
    }

    .footer-option {
      flex-wrap: wrap;
    }
    .sleep-toggle {
      min-height: 2.75rem;
    }

    .footer-actions .action-button {
      flex: 1 1 0;
      min-width: 0;
      min-height: 2.75rem;
      padding: 0.6rem 0.75rem;
    }

    .option-error {
      white-space: normal;
      overflow: visible;
    }
  }
</style>
