<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Circle, Pause, Square, Play, Eye, EyeOff, Mic } from 'lucide-svelte';
  import {
    subscribeDomainEvents,
    type DomainEvent,
    type SpeechRecognizedPayload,
  } from '../../domainEvents';

  let eventSource: EventSource | null = null;
  let videoEl: HTMLVideoElement | null = null;
  let mediaStream: MediaStream | null = null;
  let devices: MediaDeviceInfo[] = [];
  let selectedDeviceId: string | null = null;
  let recorderState: string = 'STOPPED'; // STOPPED, RECORDING, PAUSED
  let isHovered = false;
  let previewVisible: boolean = true;
  let previewToggleLabel: string = 'プレビュー映像を非表示にする';
  let cameraStartInFlight: boolean = false;
  let previewToggleFocused: boolean = false;
  let toggleVisible: boolean = true;

  // Speech recognition preview state
  type SpeechState = 'idle' | 'listening' | 'recognized';
  let speechState: SpeechState = 'idle';
  let speechText: string = '';
  let speechFadeTimeout: ReturnType<typeof setTimeout> | null = null;
  let speechListeningTimeout: ReturnType<typeof setTimeout> | null = null;
  let speechRecognizedMinTimeout: ReturnType<typeof setTimeout> | null = null;
  let speechRecognizedMinUntil: number | null = null;
  let speechPendingListeningUntil: number | null = null;
  const SPEECH_FADE_DELAY_MS = 5000;
  const SPEECH_LISTENING_TIMEOUT_MS = 2000;
  const SPEECH_RECOGNIZED_MIN_MS = 3000;

  const CAMERA_START_MAX_ATTEMPTS = 3;
  const CAMERA_START_RETRY_DELAY_MS = 500;

  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  function isAbortError(error: unknown): error is DOMException {
    return error instanceof DOMException && error.name === 'AbortError';
  }

  function togglePreviewVisibility(): void {
    previewVisible = !previewVisible;
  }

  function isSpeechDisplayAvailable(): boolean {
    return recorderState !== 'STOPPED';
  }

  function startListeningState(durationMs: number = SPEECH_LISTENING_TIMEOUT_MS): void {
    speechState = 'listening';
    if (speechFadeTimeout) {
      clearTimeout(speechFadeTimeout);
      speechFadeTimeout = null;
    }
    if (speechListeningTimeout) {
      clearTimeout(speechListeningTimeout);
    }
    speechListeningTimeout = setTimeout(() => {
      speechState = 'idle';
      speechListeningTimeout = null;
    }, durationMs);
  }

  function finishRecognizedDisplay(): void {
    speechRecognizedMinUntil = null;
    if (speechPendingListeningUntil !== null) {
      const remaining = speechPendingListeningUntil - Date.now();
      speechPendingListeningUntil = null;
      if (remaining > 0 && isSpeechDisplayAvailable()) {
        startListeningState(remaining);
        return;
      }
    }
    speechState = 'idle';
  }

  function connectRecorderStateEvents(): void {
    eventSource?.close();
    eventSource = subscribeDomainEvents((event: DomainEvent) => {
      switch (event.type) {
        case 'domain.recording.started':
        case 'domain.recording.resumed':
          recorderState = 'RECORDING';
          break;
        case 'domain.recording.paused':
          recorderState = 'PAUSED';
          break;
        case 'domain.recording.stopped':
        case 'domain.recording.cancelled':
          recorderState = 'STOPPED';
          // Reset speech preview when recording stops
          speechState = 'idle';
          speechText = '';
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
          break;
        case 'domain.speech.listening':
          // Only show listening state when recording
          if (isSpeechDisplayAvailable()) {
            if (speechState === 'recognized') {
              speechPendingListeningUntil = Date.now() + SPEECH_LISTENING_TIMEOUT_MS;
              break;
            }
            startListeningState();
          }
          break;
        case 'domain.speech.recognized': {
          const payload = event.payload as SpeechRecognizedPayload;
          if (isSpeechDisplayAvailable()) {
            speechPendingListeningUntil = null;
            if (speechListeningTimeout) {
              clearTimeout(speechListeningTimeout);
              speechListeningTimeout = null;
            }
            if (payload.text) {
              speechState = 'recognized';
              speechText = payload.text;
              speechRecognizedMinUntil = Date.now() + SPEECH_RECOGNIZED_MIN_MS;
              if (speechRecognizedMinTimeout) {
                clearTimeout(speechRecognizedMinTimeout);
                speechRecognizedMinTimeout = null;
              }
              // Auto-fade after delay
              if (speechFadeTimeout) {
                clearTimeout(speechFadeTimeout);
              }
              speechFadeTimeout = setTimeout(() => {
                speechFadeTimeout = null;
                finishRecognizedDisplay();
              }, SPEECH_FADE_DELAY_MS);
            } else {
              // No text recognized (e.g. skipped or empty), return to idle
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
                speechRecognizedMinTimeout = setTimeout(() => {
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
          break;
        }
        default:
          break;
      }
    });
    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      eventSource?.close();
      eventSource = null;
    };
  }

  async function enumerateVideoDevices(): Promise<void> {
    if (!navigator?.mediaDevices?.enumerateDevices) {
      devices = [];
      return;
    }
    try {
      let list = await navigator.mediaDevices.enumerateDevices();
      // ラベルが空だときは許可がない可能性がある -> 一度許可を要求して再列挙
      const hasLabels = list.some((d) => d.kind === 'videoinput' && d.label);
      if (!hasLabels && navigator.mediaDevices.getUserMedia) {
        try {
          const tempStream = await navigator.mediaDevices.getUserMedia({
            video: true,
          });
          // stop tracks immediately
          tempStream.getTracks().forEach((t) => t.stop());
          list = await navigator.mediaDevices.enumerateDevices();
        } catch {
          // permission denied or not available
        }
      }
      devices = list.filter((d) => d.kind === 'videoinput');
    } catch (err) {
      console.error('enumerateDevices error:', err);
      devices = [];
    }
  }

  async function startCamera(
    deviceId: string,
    retryCount: number = 0,
    forceGenericConstraints: boolean = false
  ): Promise<void> {
    const existingStream = mediaStream;
    try {
      const targetDeviceId = forceGenericConstraints ? undefined : deviceId;
      const constraints: MediaStreamConstraints = {
        video: targetDeviceId ? { deviceId: { exact: targetDeviceId } } : true,
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      mediaStream = stream;
      if (existingStream && existingStream !== stream) {
        existingStream.getTracks().forEach((track) => track.stop());
      }
      if (videoEl) {
        videoEl.srcObject = stream;
        // autoplay playsinline muted for preview
        try {
          await videoEl.play();
        } catch {
          // ignore play errors
        }
      }
    } catch (err) {
      if (isAbortError(err) && retryCount + 1 < CAMERA_START_MAX_ATTEMPTS) {
        const nextAttempt = retryCount + 1;
        await sleep(CAMERA_START_RETRY_DELAY_MS * nextAttempt);
        await enumerateVideoDevices();
        const useGenericConstraints =
          forceGenericConstraints || nextAttempt === CAMERA_START_MAX_ATTEMPTS - 1;
        await startCamera(deviceId, nextAttempt, useGenericConstraints);
        return;
      }
      console.error('startCamera error:', err);
      mediaStream = existingStream ?? null;
    }
  }

  async function ensureCameraStream(deviceId: string): Promise<void> {
    if (cameraStartInFlight || mediaStream) {
      if (videoEl && mediaStream && videoEl.srcObject === null) {
        videoEl.srcObject = mediaStream;
        void videoEl.play().catch(() => {});
      }
      return;
    }
    cameraStartInFlight = true;
    try {
      await startCamera(deviceId);
    } finally {
      cameraStartInFlight = false;
    }
  }

  function stopCamera(): void {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (videoEl) {
      try {
        videoEl.pause();
      } catch {}
      videoEl.srcObject = null;
    }
  }

  function sectionsToSettings(
    sections: unknown[] | undefined
  ): Record<string, Record<string, unknown>> {
    const out: Record<string, Record<string, unknown>> = {};
    if (!Array.isArray(sections)) return out;
    for (const sec of sections) {
      try {
        const id = (sec as { id: string }).id;
        const fields = (sec as { fields?: unknown[] }).fields || [];
        const obj: Record<string, unknown> = {};
        for (const f of fields) {
          const field = f as { id: string; value?: unknown };
          obj[field.id] = Object.hasOwn(field, 'value') ? field.value : '';
        }
        out[id] = obj;
      } catch {
        /* ignore malformed section */
      }
    }
    return out;
  }

  onMount(() => {
    (async () => {
      connectRecorderStateEvents();

      try {
        const res = await fetch('/api/settings', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          let web: Record<string, unknown> | null = null;
          if (Array.isArray(data?.sections)) {
            const all = sectionsToSettings(data.sections);
            web = all['web_server'] || {};
          }
          const name = String(web?.virtual_camera_name || 'OBS Virtual Camera');
          console.log('Configured virtual camera name:', name);
          await enumerateVideoDevices();
          const found = devices.find((d) => (d.label || '').includes(name));
          if (found) {
            selectedDeviceId = found.deviceId;
            console.log('Using virtual camera device:', found);
            await ensureCameraStream(found.deviceId);
            return;
          } else {
            console.warn(
              'Virtual camera not found:',
              name,
              'available:',
              devices.map((d) => d.label)
            );
          }
        }
      } catch (err) {
        console.error('Failed to fetch preview_mode from settings:', err);
      }
    })();
  });

  onDestroy(() => {
    if (eventSource) {
      eventSource.close();
    }
    if (speechFadeTimeout) {
      clearTimeout(speechFadeTimeout);
    }
    if (speechListeningTimeout) {
      clearTimeout(speechListeningTimeout);
    }
    if (speechRecognizedMinTimeout) {
      clearTimeout(speechRecognizedMinTimeout);
    }
    stopCamera();
  });

  $: previewToggleLabel = previewVisible
    ? 'プレビュー映像を非表示にする'
    : 'プレビュー映像を表示する';
  $: toggleVisible = previewVisible ? isHovered || previewToggleFocused : true;

  $: if (previewVisible) {
    if (!mediaStream) {
      if (selectedDeviceId) {
        void ensureCameraStream(selectedDeviceId);
      } else {
        console.warn('No selected device ID for camera stream');
      }
    } else if (videoEl && videoEl.srcObject === null) {
      videoEl.srcObject = mediaStream;
      void videoEl.play().catch(() => {});
    }
  } else {
    if (videoEl) {
      try {
        videoEl.pause();
      } catch {}
      videoEl.srcObject = null;
    }
  }

  // 録画状態に応じた表示設定
  type RecorderVisuals = {
    dotColor: string;
    label: string;
    borderColor: string;
  };

  const defaultVisuals: RecorderVisuals = {
    dotColor: 'var(--theme-preview-neutral-soft)',
    label: 'Stopped',
    borderColor: 'var(--theme-preview-neutral)',
  };

  let recorderVisuals: RecorderVisuals = defaultVisuals;

  $: recorderVisuals = getRecorderVisuals(recorderState);

  function getRecorderVisuals(state: string): RecorderVisuals {
    switch (state) {
      case 'RECORDING':
        return {
          dotColor: 'var(--theme-preview-danger)',
          label: 'Recording',
          borderColor: 'var(--theme-preview-danger)',
        };
      case 'PAUSED':
        return {
          dotColor: 'var(--theme-preview-warning)',
          label: 'Paused',
          borderColor: 'var(--theme-preview-warning)',
        };
      case 'STOPPED':
        return {
          dotColor: 'var(--theme-preview-neutral-soft)',
          label: 'Stopped',
          borderColor: 'var(--theme-preview-neutral)',
        };
      default:
        return defaultVisuals;
    }
  }

  // 手動録画操作の関数
  async function handleStartRecording(): Promise<void> {
    try {
      const response = await fetch('/api/recorder/start', { method: 'POST' });
      if (!response.ok) {
        console.error('Failed to start recording');
      }
    } catch (error) {
      console.error('Error starting recording:', error);
    }
  }

  async function handlePauseRecording(): Promise<void> {
    try {
      const response = await fetch('/api/recorder/pause', { method: 'POST' });
      if (!response.ok) {
        console.error('Failed to pause recording');
      }
    } catch (error) {
      console.error('Error pausing recording:', error);
    }
  }

  async function handleResumeRecording(): Promise<void> {
    try {
      const response = await fetch('/api/recorder/resume', { method: 'POST' });
      if (!response.ok) {
        console.error('Failed to resume recording');
      }
    } catch (error) {
      console.error('Error resuming recording:', error);
    }
  }

  async function handleStopRecording(): Promise<void> {
    try {
      const response = await fetch('/api/recorder/stop', { method: 'POST' });
      if (!response.ok) {
        console.error('Failed to stop recording');
      }
    } catch (error) {
      console.error('Error stopping recording:', error);
    }
  }

  function handlePreviewToggleMouseLeave(event: MouseEvent): void {
    const target = event.currentTarget;
    if (target instanceof HTMLButtonElement) {
      target.blur();
    }
  }
</script>

<div
  class="video-preview"
  class:preview-hidden={!previewVisible}
  style={`--preview-border-color: ${recorderVisuals.borderColor};`}
  role="button"
  aria-label="ビデオプレビューと録画コントロール"
  tabindex="0"
  on:mouseenter={() => (isHovered = true)}
  on:mouseleave={() => (isHovered = false)}
  on:focus={() => (isHovered = true)}
  on:blur={() => (isHovered = false)}
>
  <!-- 録画状態表示とコントロール -->
  <div class="status-control-bar" class:hovered={isHovered}>
    <div class="status-section">
      <Circle size={16} fill={recorderVisuals.dotColor} strokeWidth={0} />
      <span class="status-label">{recorderVisuals.label}</span>
    </div>

    <div class="controls-section" class:visible={isHovered}>
      <div class="divider"></div>

      {#if recorderState === 'STOPPED'}
        <button class="control-btn start" on:click={handleStartRecording} title="録画開始">
          <Circle size={12} fill="currentColor" />
        </button>
      {:else if recorderState === 'RECORDING'}
        <button class="control-btn pause" on:click={handlePauseRecording} title="一時停止">
          <Pause size={12} />
        </button>
        <button class="control-btn stop" on:click={handleStopRecording} title="停止">
          <Square size={12} fill="currentColor" />
        </button>
      {:else if recorderState === 'PAUSED'}
        <button class="control-btn resume" on:click={handleResumeRecording} title="再開">
          <Play size={12} fill="currentColor" />
        </button>
        <button class="control-btn stop" on:click={handleStopRecording} title="停止">
          <Square size={12} fill="currentColor" />
        </button>
      {/if}
    </div>
  </div>

  <button
    type="button"
    class="preview-toggle"
    class:preview-toggle--visible={toggleVisible}
    on:click={togglePreviewVisibility}
    on:focus={() => (previewToggleFocused = true)}
    on:blur={() => (previewToggleFocused = false)}
    on:mouseleave={handlePreviewToggleMouseLeave}
    aria-pressed={previewVisible}
    aria-label={previewToggleLabel}
    title={previewToggleLabel}
  >
    {#if previewVisible}
      <EyeOff size={200} strokeWidth={1.8} />
    {:else}
      <Eye size={200} strokeWidth={1.8} />
    {/if}
  </button>

  {#if previewVisible}
    <video bind:this={videoEl} class="preview-canvas" playsinline muted></video>
  {/if}

  <!-- Speech recognition preview overlay -->
  {#if previewVisible && speechState !== 'idle'}
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

<style>
  .video-preview {
    position: relative;
    width: 100%;
    height: 100%;
    aspect-ratio: 16 / 9;
    display: grid;
    place-items: center;
    background: var(--glass-bg-strong);
    border: 0.5rem solid var(--preview-border-color, var(--theme-preview-neutral));
    border-radius: var(--preview-radius, 24px);
    overflow: hidden;
    box-shadow:
      var(--glass-shadow, 0 20px 60px rgba(var(--theme-rgb-shadow-deep), 0.5)),
      inset 0 0 40px rgba(var(--theme-rgb-black), 0.35);
    transition: border-color 0.3s ease;
  }

  .video-preview.preview-hidden {
    background: rgba(var(--theme-rgb-surface-preview), 0.6);
    border: 2px dashed rgba(var(--theme-rgb-slate), 0.6);
    box-shadow: none;
  }

  .status-control-bar {
    position: absolute;
    top: 0.5rem;
    left: 0.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem;
    background: rgba(var(--theme-rgb-black), 0.3);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-radius: 12px;
    border: 1px solid rgba(var(--theme-rgb-white), 0.05);
    z-index: 10;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .video-preview.preview-hidden .status-control-bar {
    background: rgba(var(--theme-rgb-surface-preview), 0.7);
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border: 1px solid rgba(var(--theme-rgb-slate), 0.4);
    box-shadow: none;
  }

  .status-control-bar.hovered {
    opacity: 1;
  }

  .status-section {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  .status-label {
    color: var(--theme-color-white);
    font-size: 1rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .controls-section {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 0;
    opacity: 0;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .controls-section.visible {
    max-width: 200px;
    opacity: 1;
  }

  .divider {
    width: 1px;
    height: 24px;
    background: rgba(var(--theme-rgb-white), 0.1);
    margin: 0 4px;
  }

  .control-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    padding: 0;
    border: none;
    border-radius: 0.5rem;
    color: var(--theme-color-white);
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }

  .control-btn.start {
    background: rgba(var(--theme-rgb-red-preview), 0.8);
  }

  .control-btn.start:hover {
    background: rgba(var(--theme-rgb-red-preview), 1);
    transform: scale(1.05);
  }

  .control-btn.pause {
    background: rgba(var(--theme-rgb-amber-preview), 0.8);
  }

  .control-btn.pause:hover {
    background: rgba(var(--theme-rgb-amber-preview), 1);
    transform: scale(1.05);
  }

  .control-btn.resume {
    background: rgba(var(--theme-rgb-green-preview), 0.8);
  }

  .control-btn.resume:hover {
    background: rgba(var(--theme-rgb-green-preview), 1);
    transform: scale(1.05);
  }

  .control-btn.stop {
    background: rgba(var(--theme-rgb-gray), 0.8);
  }

  .control-btn.stop:hover {
    background: rgba(var(--theme-rgb-gray), 1);
    transform: scale(1.05);
  }

  .preview-canvas {
    display: block;
    /* Fill the preview container without distorting aspect ratio */
    width: 100%;
    height: 100%;
    max-width: none;
    max-height: none;
    /* Maintain GPU compositing for smoother preview updates */
    transform: translateZ(0);
    will-change: auto; /* keep the transform hint minimal */
    /* Prefer automatic interpolation for streamed frames */
    image-rendering: auto;
    /* Preserve 3D transform context for overlays */
    transform-style: preserve-3d;
  }

  video.preview-canvas {
    display: block;
    width: 100%;
    height: 100%;
    transform: translateZ(0);
    object-fit: contain;
    object-position: center;
    background: var(--theme-color-black);
  }

  .preview-toggle {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 14rem;
    height: 14rem;
    border-radius: 999px;
    border: none;
    background: transparent;
    color: var(--theme-color-white);
    cursor: pointer;
    opacity: 0;
    pointer-events: none;
    transition:
      opacity 0.2s ease,
      transform 0.2s ease;
    z-index: 12;
  }

  .preview-toggle--visible {
    opacity: 1;
    pointer-events: auto;
  }

  .preview-toggle--visible:hover {
    transform: translate(-50%, -50%) scale(1.05);
  }

  .preview-toggle:focus-visible {
    outline: 3px solid rgba(var(--theme-rgb-white), 0.6);
    outline-offset: 4px;
    transform: translate(-50%, -50%) scale(1.02);
  }

  /* Speech recognition preview styles */
  .speech-preview {
    position: absolute;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    max-width: calc(100% - 2rem);
    box-sizing: border-box;
    padding: 0.75rem 1.25rem;
    background: rgba(var(--theme-rgb-black), 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-radius: 12px;
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
    z-index: 15;
    animation: speech-fade-in 0.3s ease-out;
  }

  @keyframes speech-fade-in {
    from {
      opacity: 0;
      transform: translateX(-50%) translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
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
    animation: mic-pulse 1.5s ease-in-out infinite;
  }

  @keyframes mic-pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
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
    animation: dot-bounce 1.4s ease-in-out infinite both;
  }

  .speech-listening-dots .dot:nth-child(1) {
    animation-delay: 0s;
  }

  .speech-listening-dots .dot:nth-child(2) {
    animation-delay: 0.2s;
  }

  .speech-listening-dots .dot:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes dot-bounce {
    0%,
    80%,
    100% {
      transform: scale(0.8);
      opacity: 0.5;
    }
    40% {
      transform: scale(1.2);
      opacity: 1;
    }
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
</style>
