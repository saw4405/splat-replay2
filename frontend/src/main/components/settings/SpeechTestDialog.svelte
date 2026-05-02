<script lang="ts">
  import { Mic } from 'lucide-svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';

  /**
   * 音声認識テストダイアログ。
   * ダイアログを開くと自動で文字起こしを開始し、閉じると停止する。
   * 録画中のバトル字幕表示と同じ UI/UX で認識結果を表示する。
   */

  type SpeechState = 'idle' | 'listening' | 'recognized';

  interface SpeechEvent {
    type: 'listening' | 'recognized' | 'error';
    text?: string;
    detail?: string;
  }

  interface Props {
    open?: boolean;
    speechSettings?: Record<string, unknown>;
  }

  let { open = $bindable(false), speechSettings = {} }: Props = $props();

  const micDeviceName = $derived((speechSettings?.mic_device_name as string) ?? '');

  // バトル中の字幕表示と同じタイミング定数
  const SPEECH_FADE_DELAY_MS = 5000;
  const SPEECH_LISTENING_TIMEOUT_MS = 2000;
  const SPEECH_RECOGNIZED_MIN_MS = 3000;

  let speechState = $state<SpeechState>('idle');
  let speechText = $state<string>('');
  let errorMessage = $state('');
  let streaming = $state(false);
  let abortController: AbortController | null = null;

  // タイマー管理
  let speechFadeTimeout: number | null = null;
  let speechListeningTimeout: number | null = null;
  let speechRecognizedMinTimeout: number | null = null;
  let speechRecognizedMinUntil: number | null = null;
  let speechPendingListeningUntil: number | null = null;

  // ダイアログの開閉に連動して文字起こしを自動開始・停止する
  $effect(() => {
    if (open) {
      void startStream();
    } else {
      stopStream();
      resetState();
    }
  });

  function resetState(): void {
    speechState = 'idle';
    speechText = '';
    errorMessage = '';
    streaming = false;
    clearAllTimers();
  }

  function clearAllTimers(): void {
    if (speechFadeTimeout) {
      clearTimeout(speechFadeTimeout);
      speechFadeTimeout = null;
    }
    if (speechListeningTimeout) {
      clearTimeout(speechListeningTimeout);
      speechListeningTimeout = null;
    }
    if (speechRecognizedMinTimeout) {
      clearTimeout(speechRecognizedMinTimeout);
      speechRecognizedMinTimeout = null;
    }
    speechRecognizedMinUntil = null;
    speechPendingListeningUntil = null;
  }

  // --- バトル中の字幕表示と同じ状態遷移ロジック ---

  function startListeningState(durationMs: number = SPEECH_LISTENING_TIMEOUT_MS): void {
    speechState = 'listening';
    if (speechFadeTimeout) {
      clearTimeout(speechFadeTimeout);
      speechFadeTimeout = null;
    }
    if (speechListeningTimeout) {
      clearTimeout(speechListeningTimeout);
    }
    speechListeningTimeout = window.setTimeout(() => {
      speechState = 'idle';
      speechListeningTimeout = null;
    }, durationMs);
  }

  function finishRecognizedDisplay(): void {
    speechRecognizedMinUntil = null;
    if (speechPendingListeningUntil !== null) {
      const remaining = speechPendingListeningUntil - Date.now();
      speechPendingListeningUntil = null;
      if (remaining > 0 && streaming) {
        startListeningState(remaining);
        return;
      }
    }
    speechState = 'idle';
  }

  function handleListeningEvent(): void {
    if (!streaming) return;
    if (speechState === 'recognized') {
      speechPendingListeningUntil = Date.now() + SPEECH_LISTENING_TIMEOUT_MS;
      return;
    }
    startListeningState();
  }

  function handleRecognizedEvent(text: string | undefined): void {
    if (!streaming) return;
    speechPendingListeningUntil = null;
    if (speechListeningTimeout) {
      clearTimeout(speechListeningTimeout);
      speechListeningTimeout = null;
    }
    if (text) {
      speechState = 'recognized';
      speechText = text;
      speechRecognizedMinUntil = Date.now() + SPEECH_RECOGNIZED_MIN_MS;
      if (speechRecognizedMinTimeout) {
        clearTimeout(speechRecognizedMinTimeout);
        speechRecognizedMinTimeout = null;
      }
      if (speechFadeTimeout) {
        clearTimeout(speechFadeTimeout);
      }
      speechFadeTimeout = window.setTimeout(() => {
        speechFadeTimeout = null;
        finishRecognizedDisplay();
      }, SPEECH_FADE_DELAY_MS);
    } else {
      // テキストなし（スキップまたは空）
      if (
        speechState === 'recognized' &&
        speechRecognizedMinUntil !== null &&
        Date.now() < speechRecognizedMinUntil
      ) {
        const remaining = speechRecognizedMinUntil - Date.now();
        if (speechRecognizedMinTimeout) {
          clearTimeout(speechRecognizedMinTimeout);
        }
        if (speechFadeTimeout) {
          clearTimeout(speechFadeTimeout);
          speechFadeTimeout = null;
        }
        speechRecognizedMinTimeout = window.setTimeout(() => {
          speechRecognizedMinTimeout = null;
          finishRecognizedDisplay();
        }, remaining);
      } else {
        if (speechFadeTimeout) {
          clearTimeout(speechFadeTimeout);
          speechFadeTimeout = null;
        }
        if (speechRecognizedMinTimeout) {
          clearTimeout(speechRecognizedMinTimeout);
          speechRecognizedMinTimeout = null;
        }
        finishRecognizedDisplay();
      }
    }
  }

  // --- ストリーム接続 ---

  async function startStream(): Promise<void> {
    streaming = true;
    errorMessage = '';

    abortController = new AbortController();

    try {
      const response = await fetch('/api/settings/speech/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mic_device_name: micDeviceName,
          overrides: speechSettings,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        let detail = `status ${response.status}`;
        try {
          const body = await response.json();
          if (typeof body.detail === 'string') {
            detail = body.detail;
          }
        } catch {
          // JSON パース失敗時はデフォルトメッセージを使用
        }
        throw new Error(detail);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('レスポンスのストリームを取得できませんでした。');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line) as SpeechEvent;

          if (event.type === 'listening') {
            handleListeningEvent();
          } else if (event.type === 'recognized') {
            handleRecognizedEvent(event.text);
          } else if (event.type === 'error') {
            throw new Error(event.detail ?? '音声認識テストに失敗しました。');
          }
        }
      }

      streaming = false;
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        streaming = false;
        return;
      }
      errorMessage = err instanceof Error ? err.message : '音声認識テストに失敗しました。';
      streaming = false;
    } finally {
      abortController = null;
    }
  }

  function stopStream(): void {
    abortController?.abort();
    abortController = null;
    streaming = false;
    clearAllTimers();
  }

  function handleClose(): void {
    open = false;
  }
</script>

<BaseDialog
  bind:open
  title="音声認識テスト"
  footerVariant="compact"
  primaryButtonText="閉じる"
  onPrimaryClick={handleClose}
  maxWidth="40rem"
  maxHeight="auto"
  minHeight="auto"
>
  <div class="speech-test-content" data-testid="speech-test-dialog">
    <!-- バトル中のプレビュー画面を模した字幕表示エリア -->
    <div class="preview-area">
      <div class="preview-surface">
        {#if speechState !== 'idle'}
          <div
            class="speech-preview"
            class:speech-preview--listening={speechState === 'listening'}
            class:speech-preview--recognized={speechState === 'recognized'}
          >
            {#if speechState === 'listening'}
              <div class="speech-listening">
                <Mic size={16} class="speech-mic-icon" />
                <span class="speech-listening-text">音声認識中...</span>
                <div class="speech-listening-dots">
                  <span class="dot"></span>
                  <span class="dot"></span>
                  <span class="dot"></span>
                </div>
              </div>
            {:else if speechState === 'recognized'}
              <div class="speech-text">{speechText}</div>
            {/if}
          </div>
        {/if}
      </div>
    </div>

    <div class="info-area">
      <p class="mic-info">マイク: <span class="mic-name">{micDeviceName}</span></p>
      {#if errorMessage}
        <p class="error-text">{errorMessage}</p>
      {/if}
    </div>
  </div>
</BaseDialog>

<style>
  .speech-test-content {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 0.5rem 0;
  }

  .preview-area {
    width: 100%;
  }

  .preview-surface {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    background:
      radial-gradient(circle at top, rgba(var(--theme-rgb-accent), 0.08), transparent 52%),
      linear-gradient(
        135deg,
        rgba(var(--theme-rgb-surface-preview), 0.78) 0%,
        rgba(var(--theme-rgb-black), 0.6) 100%
      );
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(var(--theme-rgb-white), 0.08);
  }

  /* バトル中の字幕オーバーレイと同じスタイル */
  .speech-preview {
    position: absolute;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    max-width: calc(100% - 2rem);
    box-sizing: border-box;
    padding: 0.75rem 1.25rem;
    background: rgba(var(--theme-rgb-black), 0.75);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-radius: 12px;
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
    z-index: 15;
  }

  .speech-preview--listening {
    border-color: rgba(var(--theme-rgb-blue-preview), 0.4);
  }

  .speech-preview--recognized {
    border-color: rgba(var(--theme-rgb-green-preview), 0.4);
  }

  .speech-listening {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: rgba(var(--theme-rgb-white), 0.9);
  }

  .speech-preview :global(.speech-mic-icon) {
    color: var(--theme-status-info-strong);
    opacity: 0.9;
  }

  .speech-listening-text {
    font-size: 0.875rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .speech-listening-dots {
    display: flex;
    gap: 4px;
    margin-left: 4px;
  }

  .speech-listening-dots .dot {
    width: 4px;
    height: 4px;
    background: var(--theme-status-info-strong);
    border-radius: 50%;
    opacity: 0.75;
  }

  .speech-text {
    color: var(--theme-color-white);
    font-size: 1.5rem;
    font-weight: 500;
    text-align: center;
    line-height: 1.4;
    word-break: break-word;
    text-shadow: 0 1px 2px rgba(var(--theme-rgb-black), 0.5);
  }

  .info-area {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .mic-info {
    color: rgba(var(--theme-rgb-light-slate), 0.6);
    font-size: 0.85rem;
    margin: 0;
  }

  .mic-name {
    color: rgba(var(--theme-rgb-light-slate), 0.85);
    font-weight: 500;
  }

  .error-text {
    color: var(--theme-status-danger-soft, #f87171);
    font-size: 0.9rem;
    margin: 0;
  }
</style>
