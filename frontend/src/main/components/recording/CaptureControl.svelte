<script lang="ts">
  import { Circle, Gamepad2, LoaderCircle, Pause, Play, Square, Unplug } from 'lucide-svelte';
  import type { RecorderState, SwitchPowerState } from '../../api/types';

  type CaptureState =
    | 'armed'
    | 'waiting-for-power'
    | 'recording'
    | 'paused'
    | 'disconnected'
    | 'checking';

  type Props = {
    recorderState: RecorderState;
    switchPowerState: SwitchPowerState;
    onStart: () => void | Promise<void>;
    onPause: () => void | Promise<void>;
    onResume: () => void | Promise<void>;
    onStop: () => void | Promise<void>;
  };

  let { recorderState, switchPowerState, onStart, onPause, onResume, onStop }: Props = $props();

  let controlRoot = $state<HTMLDivElement | null>(null);
  let triggerButton = $state<HTMLButtonElement | null>(null);
  let isFocusWithin = $state(false);
  let isTappedOpen = $state(false);
  let suppressPassiveOpen = $state(false);
  let lastPointerType: string | null = null;

  const captureState = $derived(resolveCaptureState(recorderState, switchPowerState));
  const hasManualActions = $derived(
    captureState === 'armed' || captureState === 'recording' || captureState === 'paused'
  );
  const isExpanded = $derived(
    hasManualActions && (isTappedOpen || (!suppressPassiveOpen && isFocusWithin))
  );
  const accessibleState = $derived(getAccessibleState(captureState));

  $effect(() => {
    if (!hasManualActions) {
      isTappedOpen = false;
      suppressPassiveOpen = false;
    }
  });

  function resolveCaptureState(
    currentRecorderState: RecorderState,
    currentSwitchPowerState: SwitchPowerState
  ): CaptureState {
    if (currentSwitchPowerState === 'capture_disconnected') {
      return 'disconnected';
    }
    if (currentRecorderState === 'PAUSED') {
      return 'paused';
    }
    if (currentRecorderState === 'RECORDING') {
      return 'recording';
    }
    if (currentSwitchPowerState === 'unknown' || currentSwitchPowerState === 'stopped') {
      return 'checking';
    }
    if (currentSwitchPowerState === 'waiting_for_power_on') {
      return 'waiting-for-power';
    }
    return 'armed';
  }

  function getAccessibleState(state: CaptureState): string {
    switch (state) {
      case 'armed':
        return '次のバトルを自動録画する準備ができています';
      case 'waiting-for-power':
        return 'Switchの電源が入っていません';
      case 'recording':
        return '現在録画中です';
      case 'paused':
        return '録画を一時停止しています';
      case 'disconnected':
        return 'キャプチャーデバイスが未接続です';
      case 'checking':
        return '録画状態を確認しています';
    }
  }

  function getTriggerLabel(): string {
    return `${accessibleState}。手動録画操作を開く`;
  }

  function handlePointerDown(event: PointerEvent): void {
    lastPointerType = event.pointerType;
    if (event.pointerType !== 'mouse') {
      suppressPassiveOpen = true;
    }
  }

  function handleTriggerClick(): void {
    if (lastPointerType === 'touch' || lastPointerType === 'pen') {
      isTappedOpen = !isTappedOpen;
      suppressPassiveOpen = !isTappedOpen;
    }
    lastPointerType = null;
  }

  function handleFocusIn(): void {
    isFocusWithin = true;
  }

  function handleFocusOut(event: FocusEvent): void {
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && controlRoot?.contains(nextTarget)) {
      return;
    }
    isFocusWithin = false;
    isTappedOpen = false;
    suppressPassiveOpen = false;
  }

  function handleKeyDown(event: KeyboardEvent): void {
    if (event.key !== 'Escape' || !isExpanded) {
      return;
    }
    event.preventDefault();
    isTappedOpen = false;
    suppressPassiveOpen = true;
    triggerButton?.focus();
  }
</script>

<div
  bind:this={controlRoot}
  class={`capture-control capture-control--${captureState}`}
  class:expanded={isExpanded}
  class:no-actions={!hasManualActions}
  data-testid="capture-control"
  data-capture-state={captureState}
  role="group"
  aria-label="録画状態と手動録画操作"
>
  {#if hasManualActions}
    <button
      bind:this={triggerButton}
      type="button"
      class="capture-beacon"
      aria-label={getTriggerLabel()}
      aria-expanded={isExpanded}
      onclick={handleTriggerClick}
      onpointerdown={handlePointerDown}
      onfocusin={handleFocusIn}
      onfocusout={handleFocusOut}
      onkeydown={handleKeyDown}
    >
      <span class="capture-symbol" aria-hidden="true">
        {#if captureState === 'armed'}
          <Gamepad2 size={19} strokeWidth={2.2} />
        {:else if captureState === 'recording'}
          <span class="recording-dot"></span>
        {:else}
          <Pause size={18} fill="currentColor" strokeWidth={0} />
        {/if}
      </span>
      {#if captureState === 'armed'}
        <span class="capture-label">READY</span>
      {:else if captureState === 'recording'}
        <span class="capture-label">REC</span>
      {:else if captureState === 'paused'}
        <span class="capture-label">PAUSE</span>
      {/if}
    </button>
  {:else}
    <div class="capture-beacon" role="img" aria-label={accessibleState}>
      <span class="capture-symbol" aria-hidden="true">
        {#if captureState === 'waiting-for-power'}
          <span class="power-off-symbol">
            <Gamepad2 size={19} strokeWidth={2.2} />
          </span>
        {:else if captureState === 'disconnected'}
          <Unplug size={18} strokeWidth={2.2} />
        {:else}
          <span class="checking-icon">
            <LoaderCircle size={18} strokeWidth={2.2} />
          </span>
        {/if}
      </span>
      {#if captureState === 'waiting-for-power'}
        <span class="capture-label">POWER OFF</span>
      {:else if captureState === 'disconnected'}
        <span class="capture-label">未接続</span>
      {:else if captureState === 'checking'}
        <span class="capture-label">CHECKING</span>
      {/if}
    </div>
  {/if}

  <span class="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
    {accessibleState}
  </span>

  {#if hasManualActions}
    <div class="manual-divider" aria-hidden="true"></div>
    <div
      class="manual-actions"
      class:visible={isExpanded}
      role="toolbar"
      aria-label="手動録画操作"
      aria-hidden={!isExpanded}
      onfocusin={handleFocusIn}
      onfocusout={handleFocusOut}
      onkeydown={handleKeyDown}
    >
      {#if captureState === 'armed'}
        <button
          type="button"
          class="manual-action manual-action--start"
          aria-label="手動録画を開始"
          title="手動録画を開始"
          onclick={() => void onStart()}
        >
          <Circle size={16} fill="currentColor" aria-hidden="true" />
        </button>
      {:else if captureState === 'recording'}
        <button
          type="button"
          class="manual-action"
          aria-label="録画を一時停止"
          title="録画を一時停止"
          onclick={() => void onPause()}
        >
          <Pause size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          class="manual-action"
          aria-label="録画を停止"
          title="録画を停止"
          onclick={() => void onStop()}
        >
          <Square size={15} fill="currentColor" aria-hidden="true" />
        </button>
      {:else}
        <button
          type="button"
          class="manual-action"
          aria-label="録画を再開"
          title="録画を再開"
          onclick={() => void onResume()}
        >
          <Play size={16} fill="currentColor" aria-hidden="true" />
        </button>
        <button
          type="button"
          class="manual-action"
          aria-label="録画を停止"
          title="録画を停止"
          onclick={() => void onStop()}
        >
          <Square size={15} fill="currentColor" aria-hidden="true" />
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .capture-control {
    position: absolute;
    top: 0.875rem;
    left: 0.875rem;
    z-index: 20;
    display: inline-flex;
    align-items: center;
    min-width: 3rem;
    height: 3rem;
    overflow: hidden;
    border: 1px solid rgba(var(--theme-rgb-white), 0.2);
    border-radius: 999px;
    background: rgba(var(--theme-rgb-black), 0.72);
    color: var(--theme-preview-neutral-soft);
    box-shadow: 0 0.5rem 1.75rem rgba(var(--theme-rgb-black), 0.26);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }

  .capture-control--armed {
    color: var(--theme-preview-accent);
  }

  .capture-control--waiting-for-power {
    color: var(--theme-preview-neutral);
  }

  .capture-control--recording {
    color: var(--theme-preview-danger);
  }

  .capture-control--paused {
    color: var(--theme-preview-warning);
  }

  .capture-control--disconnected {
    color: var(--theme-preview-neutral-soft);
  }

  .capture-beacon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 2.875rem;
    height: 2.5rem;
    box-sizing: border-box;
    padding: 0 0.6875rem;
    border: 0;
    border-radius: 999px;
    background: transparent;
    color: inherit;
    font: inherit;
  }

  button.capture-beacon {
    cursor: pointer;
  }

  button.capture-beacon:hover {
    background: rgba(var(--theme-rgb-white), 0.06);
  }

  button.capture-beacon:focus-visible,
  .manual-action:focus-visible {
    outline: none;
    box-shadow:
      inset 0 0 0 2px rgba(var(--theme-rgb-black), 0.9),
      inset 0 0 0 4px rgba(var(--theme-rgb-accent), 0.75);
  }

  .capture-symbol {
    position: relative;
    display: grid;
    flex: 0 0 1.125rem;
    width: 1.125rem;
    place-items: center;
  }

  .power-off-symbol {
    position: relative;
    display: grid;
    place-items: center;
  }

  .power-off-symbol::after {
    content: '';
    position: absolute;
    width: 1.45rem;
    height: 0.125rem;
    border-radius: 999px;
    background: currentColor;
    box-shadow: 0 0 0 2px rgba(var(--theme-rgb-black), 0.72);
    transform: rotate(-45deg);
  }

  .recording-dot {
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 0.75rem currentColor;
  }

  .capture-label {
    margin-left: 0.5rem;
    color: currentColor;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.035em;
    white-space: nowrap;
  }

  .manual-divider {
    width: 1px;
    height: 1.25rem;
    margin-right: 0.125rem;
    background: rgba(var(--theme-rgb-white), 0.18);
    opacity: 0;
    transition: opacity 160ms ease;
  }

  .capture-control.expanded .manual-divider {
    opacity: 1;
  }

  .manual-actions {
    display: flex;
    flex: 0 0 auto;
    flex-wrap: nowrap;
    align-items: center;
    gap: 0.25rem;
    min-width: 0;
    max-width: 0;
    padding-right: 0;
    overflow: hidden;
    opacity: 0;
    pointer-events: none;
    visibility: hidden;
    transition:
      max-width 220ms ease,
      padding-right 220ms ease,
      opacity 160ms ease;
  }

  .manual-actions.visible {
    max-width: 5.5rem;
    padding-right: 0.25rem;
    opacity: 1;
    pointer-events: auto;
    visibility: visible;
  }

  .manual-action {
    display: grid;
    flex: 0 0 2.5rem;
    width: 2.5rem;
    height: 2.5rem;
    padding: 0;
    border: 0;
    border-radius: 999px;
    background: transparent;
    color: var(--theme-color-white);
    cursor: pointer;
  }

  .manual-action:hover {
    background: rgba(var(--theme-rgb-white), 0.1);
  }

  .manual-action--start {
    color: var(--theme-preview-danger);
  }

  .checking-icon {
    display: inline-flex;
    animation: capture-check 700ms linear infinite;
  }

  .visually-hidden {
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

  @keyframes capture-check {
    to {
      transform: rotate(360deg);
    }
  }

  @media (hover: hover) and (pointer: fine) {
    .capture-control:hover .manual-divider {
      opacity: 1;
    }

    .capture-control:hover .manual-actions {
      max-width: 5.5rem;
      padding-right: 0.25rem;
      opacity: 1;
      pointer-events: auto;
      visibility: visible;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .manual-divider,
    .manual-actions {
      transition: none;
      animation: none;
    }
  }
</style>
