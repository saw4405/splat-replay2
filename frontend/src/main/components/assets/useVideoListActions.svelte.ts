/**
 * 動画リスト共通アクション composable
 *
 * RecordedDataList / EditedDataList で重複していた以下のロジックを集約する:
 * - モーダル開閉状態管理（動画プレイヤー・サムネイルズーム・アラート・確認ダイアログ）
 * - 削除フロー（確認 → API 呼び出し → 再読み込み / エラー表示）
 * - 画像読み込みエラー処理
 * - モーダル開閉コールバックの追跡
 */

/** 動画データの最低限のインターフェース */
export interface VideoBase {
  id: string;
  filename: string;
  path: string;
}

/** createVideoListActions に渡す設定オブジェクト */
export interface VideoListActionsConfig<TVideo extends VideoBase> {
  getThumbnailUrl: (filename: string) => string;
  getVideoUrl: (videoId: string) => string;
  deleteVideo: (video: TVideo) => Promise<void>;
  onRefresh?: () => void;
  onModalOpen?: () => void;
  onModalClose?: () => void;
  /** 追加モーダルの開閉状態（例: メタデータダイアログ・字幕エディタ） */
  extraModalOpen?: () => boolean;
}

/**
 * 動画リストの共通アクションを生成するファクトリ関数
 *
 * .svelte.ts ファイルなので Svelte 5 runes（$state / $derived / $effect）が使用可能。
 */
export function createVideoListActions<TVideo extends VideoBase>(
  config: VideoListActionsConfig<TVideo>
) {
  // --- リアクティブ状態 ---
  let showVideoPlayer = $state(false);
  let showThumbnailZoom = $state(false);
  let showAlertDialog = $state(false);
  let showConfirmDialog = $state(false);
  let alertMessage = $state('');
  let alertVariant = $state<'info' | 'success' | 'warning' | 'error'>('info');
  let confirmMessage = $state('');
  let currentVideoUrl = $state('');
  let currentThumbnailUrl = $state('');
  let deletingVideoId = $state<string | null>(null);

  // 削除待ちの動画（内部状態）
  let pendingDeleteVideo = $state<TVideo | null>(null);

  // $state ではなく普通の変数で保持することで、$effect の依存ループを避ける
  let wasModalOpen = false;

  // --- 派生値 ---
  /** いずれかのモーダルが開いているかどうか（追加モーダルも含む） */
  const isAnyModalOpen = $derived(
    showVideoPlayer ||
      showThumbnailZoom ||
      showAlertDialog ||
      showConfirmDialog ||
      (config.extraModalOpen?.() ?? false)
  );

  // --- 副作用 ---
  $effect(() => {
    // isAnyModalOpen は $derived（非 $state）なので、wasModalOpen への書き込みで再実行されない
    if (isAnyModalOpen && !wasModalOpen) {
      config.onModalOpen?.();
      wasModalOpen = true;
    } else if (!isAnyModalOpen && wasModalOpen) {
      config.onModalClose?.();
      wasModalOpen = false;
    }
  });

  // --- ハンドラ ---

  /** 画像読み込みエラー時にフォールバック SVG を表示する */
  function handleImageError(e: Event): void {
    const img = e.currentTarget as HTMLImageElement;
    img.src =
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='90'%3E%3Crect fill='%23333' width='160' height='90'/%3E%3Ctext fill='%23666' x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='12'%3ENo Image%3C/text%3E%3C/svg%3E";
  }

  /** 動画プレイヤーモーダルを開く */
  function handlePlayVideo(video: TVideo): void {
    currentVideoUrl = config.getVideoUrl(video.id);
    showVideoPlayer = true;
  }

  /** サムネイルズームモーダルを開く */
  function handleZoomThumbnail(video: TVideo): void {
    currentThumbnailUrl = config.getThumbnailUrl(video.filename);
    showThumbnailZoom = true;
  }

  /** 削除確認ダイアログを表示する */
  function handleDeleteVideo(event: MouseEvent, video: TVideo): void {
    event.stopPropagation();
    confirmMessage = `「${video.filename}」を削除してもよろしいですか？\nこの操作は取り消せません。`;
    pendingDeleteVideo = video;
    showConfirmDialog = true;
  }

  /** 削除を確定する */
  async function confirmDelete(): Promise<void> {
    if (!pendingDeleteVideo) return;

    const video = pendingDeleteVideo;
    deletingVideoId = video.id;
    showConfirmDialog = false;
    pendingDeleteVideo = null;

    try {
      await config.deleteVideo(video);
      config.onRefresh?.();
    } catch (error) {
      alertMessage = `動画の削除に失敗しました: ${error}`;
      alertVariant = 'error';
      showAlertDialog = true;
    } finally {
      deletingVideoId = null;
    }
  }

  /** 削除をキャンセルする */
  function cancelDelete(): void {
    showConfirmDialog = false;
    pendingDeleteVideo = null;
  }

  // --- 公開インターフェース ---
  // getter/setter ペアで $state 変数をリアクティブに公開する
  return {
    get showVideoPlayer() {
      return showVideoPlayer;
    },
    set showVideoPlayer(v: boolean) {
      showVideoPlayer = v;
    },
    get showThumbnailZoom() {
      return showThumbnailZoom;
    },
    set showThumbnailZoom(v: boolean) {
      showThumbnailZoom = v;
    },
    get showAlertDialog() {
      return showAlertDialog;
    },
    set showAlertDialog(v: boolean) {
      showAlertDialog = v;
    },
    get showConfirmDialog() {
      return showConfirmDialog;
    },
    set showConfirmDialog(v: boolean) {
      showConfirmDialog = v;
    },
    get alertMessage() {
      return alertMessage;
    },
    set alertMessage(v: string) {
      alertMessage = v;
    },
    get alertVariant() {
      return alertVariant;
    },
    set alertVariant(v: 'info' | 'success' | 'warning' | 'error') {
      alertVariant = v;
    },
    get confirmMessage() {
      return confirmMessage;
    },
    get currentVideoUrl() {
      return currentVideoUrl;
    },
    set currentVideoUrl(v: string) {
      currentVideoUrl = v;
    },
    get currentThumbnailUrl() {
      return currentThumbnailUrl;
    },
    get deletingVideoId() {
      return deletingVideoId;
    },
    handleImageError,
    handlePlayVideo,
    handleZoomThumbnail,
    handleDeleteVideo,
    confirmDelete,
    cancelDelete,
  };
}
