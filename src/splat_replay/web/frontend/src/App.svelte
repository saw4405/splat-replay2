<script lang="ts">
  import { onMount } from 'svelte';
  import { requestAutoRecorderStart, type AutoRecorderStartResponse } from '$lib/api';

  const PREVIEW_ENDPOINT = '/api/preview/stream';

  let status: AutoRecorderStartResponse = {
    ok: false,
    error: null,
    message: '初期化中です…',
    waiting_for_device: false
  };

  let isRequesting = false;
  let previewKey = Date.now();
  let previewError = '';

  async function startAutoRecorder(): Promise<void> {
    if (isRequesting) {
      return;
    }

    isRequesting = true;
    previewError = '';
    status = {
      ok: false,
      error: null,
      message: '自動録画を起動しています…',
      waiting_for_device: false
    };

    try {
      const response = await requestAutoRecorderStart();
      status = response;
    } catch (error) {
      console.error('自動録画の開始リクエストに失敗しました。', error);
      status = {
        ok: false,
        error: '自動録画の開始リクエストに失敗しました。',
        message: '自動録画の開始リクエストに失敗しました。',
        waiting_for_device: false
      };
    } finally {
      isRequesting = false;
    }
  }

  function handlePreviewError(): void {
    previewError = 'プレビューの受信に失敗しました。ブラウザを更新するか、プレビュー再接続を試してください。';
  }

  function reconnectPreview(): void {
    previewError = '';
    previewKey = Date.now();
  }

  $: statusMessage = status.message ?? (status.ok ? '自動録画が開始されました。' : '自動録画の開始に失敗しました。');
  $: isWaiting = status.waiting_for_device;

  onMount(() => {
    void startAutoRecorder();
  });
</script>

<main>
  <header>
    <h1>自動録画プレビュー</h1>
    <p class="lead">自動録画をバックグラウンドで開始し、OBS 仮想カメラからのライブ映像を表示します。</p>
  </header>

  <section class="status-section">
    <div class={`status ${status.ok ? 'success' : 'info'} ${status.error ? 'error' : ''}`}>
      <p>{statusMessage}</p>
      {#if isWaiting}
        <p class="hint">キャプチャデバイスが接続されるまで待機しています。スイッチやキャプチャカードの電源を確認してください。</p>
      {/if}
      {#if status.error && !isWaiting}
        <p class="hint">{status.error}</p>
      {/if}
    </div>
    <div class="actions">
      <button class="primary" on:click={startAutoRecorder} disabled={isRequesting}>
        {isRequesting ? '要求中…' : '自動録画を再リクエスト'}
      </button>
      <button class="secondary" on:click={reconnectPreview}>
        プレビュー再接続
      </button>
    </div>
  </section>

  <section class="preview-section">
    <div class="preview-frame">
      <img
        src={`${PREVIEW_ENDPOINT}?key=${previewKey}`}
        alt="ライブプレビュー"
        on:error={handlePreviewError}
      />
      {#if previewError}
        <div class="overlay">{previewError}</div>
      {/if}
    </div>
    <p class="note">プレビューは MJPEG 形式で配信されます。映像が更新されない場合は「プレビュー再接続」を押してください。</p>
  </section>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: 'Noto Sans JP', system-ui, sans-serif;
    background: #10151c;
    color: #f5f6f8;
  }

  main {
    padding: 2.5rem 1.5rem 3rem;
    max-width: 960px;
    margin: 0 auto;
  }

  header {
    margin-bottom: 2rem;
  }

  h1 {
    margin: 0 0 0.5rem;
    font-size: 2rem;
  }

  .lead {
    margin: 0;
    color: #c7d0dd;
  }

  .status-section {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }

  .status {
    padding: 1rem 1.25rem;
    border-radius: 8px;
    background: rgba(41, 52, 98, 0.65);
    border: 1px solid rgba(120, 146, 255, 0.35);
  }

  .status.success {
    background: rgba(39, 82, 60, 0.65);
    border-color: rgba(46, 204, 113, 0.4);
  }

  .status.error {
    background: rgba(94, 46, 46, 0.7);
    border-color: rgba(231, 76, 60, 0.6);
  }

  .status p {
    margin: 0;
    line-height: 1.6;
  }

  .hint {
    margin-top: 0.6rem;
    color: #f5f6f8;
    font-size: 0.9rem;
    opacity: 0.9;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.25rem;
    flex-wrap: wrap;
  }

  button {
    border: none;
    border-radius: 8px;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    cursor: pointer;
    transition: transform 0.2s ease, opacity 0.2s ease;
  }

  button.primary {
    background: linear-gradient(135deg, #5373f4, #7f53f4);
    color: #ffffff;
  }

  button.secondary {
    background: rgba(255, 255, 255, 0.1);
    color: #f5f6f8;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button:not(:disabled):hover {
    transform: translateY(-2px);
  }

  .preview-section {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }

  .preview-frame {
    position: relative;
    background: #000000;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .preview-frame img {
    display: block;
    width: 100%;
    height: auto;
    object-fit: contain;
    background: #000000;
  }

  .overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 1rem;
    background: rgba(0, 0, 0, 0.6);
  }

  .note {
    margin-top: 0.75rem;
    color: #c7d0dd;
    font-size: 0.9rem;
  }
</style>
