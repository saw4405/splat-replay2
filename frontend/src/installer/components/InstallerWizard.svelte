<script lang="ts">
  import { onMount } from "svelte";
  import { ChevronLeft, ChevronRight, SkipForward } from "lucide-svelte";
  import {
    installationState,
    isLoading,
    error,
    progressInfo,
    fetchInstallationStatus,
    goToNextStep,
    goToPreviousStep,
    skipCurrentStep,
    executeStep,
    completeInstallation,
    clearError,
  } from "../store";
  import { InstallationStep } from "../types";
  import ErrorDialog from "./ErrorDialog.svelte";
  import ConfirmDialog from "./ConfirmDialog.svelte";
  import CompletionDialog from "./CompletionDialog.svelte";
  import StepProgress from "./StepProgress.svelte";

  // ステップコンポーネントのスロット
  export let currentStepComponent: any = null;

  let showSkipConfirm = false;
  let showErrorDialog = false;
  let showCompletionDialog = false;

  $: if ($error) {
    showErrorDialog = true;
  }

  $: canGoBack = $installationState
    ? $installationState.current_step !== InstallationStep.HARDWARE_CHECK
    : false;

  $: canSkip = $installationState
    ? $installationState.current_step === InstallationStep.FONT_INSTALLATION ||
      $installationState.current_step === InstallationStep.YOUTUBE_SETUP
    : false;

  $: isLastStep = $installationState
    ? $installationState.current_step === InstallationStep.YOUTUBE_SETUP
    : false;

  onMount(async () => {
    await fetchInstallationStatus();
  });

  async function handleNext(): Promise<void> {
    // 現在のステップを完了としてマークしてから次へ進む
    if ($installationState) {
      try {
        await executeStep($installationState.current_step);
      } catch (err) {
        // エラーは既にストアで処理されているので、ここでは何もしない
        console.error("Failed to complete step:", err);
        return;
      }

      // 最後のステップの場合は完了処理
      if (isLastStep) {
        await completeInstallation();
        showCompletionDialog = true;
        return;
      }
    }
    await goToNextStep();
  }

  async function handleBack(): Promise<void> {
    await goToPreviousStep();
  }

  function handleSkipClick(): void {
    showSkipConfirm = true;
  }

  async function handleSkipConfirm(): Promise<void> {
    await skipCurrentStep();

    // 最後のステップをスキップした場合は完了処理
    if (isLastStep) {
      await completeInstallation();
      showCompletionDialog = true;
    } else {
      await goToNextStep();
    }
  }

  function handleErrorClose(): void {
    showErrorDialog = false;
    clearError();
  }

  async function handleErrorRetry(): Promise<void> {
    showErrorDialog = false;
    clearError();
    await fetchInstallationStatus();
  }

  function handleCompletionContinue(): void {
    // ページをリロードしてメインアプリに遷移
    window.location.reload();
  }
</script>

<div class="installer-wizard glass-surface">
  <div class="wizard-header">
    <h1 class="wizard-title">Splat Replay セットアップ</h1>
  </div>

  <div class="wizard-progress">
    <StepProgress progress={$progressInfo} />
  </div>

  <div class="wizard-content">
    {#if $isLoading && !$installationState}
      <div class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">読み込み中...</p>
      </div>
    {:else if $installationState}
      <div class="step-container">
        <slot name="step-content">
          {#if currentStepComponent}
            <svelte:component this={currentStepComponent} />
          {:else}
            <div class="placeholder-content">
              <p>ステップコンテンツがありません</p>
            </div>
          {/if}
        </slot>
      </div>
    {:else}
      <div class="error-container">
        <p class="error-text">インストール状態を読み込めませんでした</p>
      </div>
    {/if}
  </div>

  <div class="wizard-footer">
    <div class="footer-actions">
      <button
        class="button button-secondary"
        type="button"
        disabled={!canGoBack || $isLoading}
        on:click={handleBack}
      >
        <ChevronLeft class="button-icon" size={20} />
        戻る
      </button>

      <div class="footer-spacer"></div>

      {#if canSkip}
        <button
          class="button button-skip"
          type="button"
          disabled={$isLoading}
          on:click={handleSkipClick}
        >
          <SkipForward class="button-icon" size={20} />
          スキップ
        </button>
      {/if}

      <button
        class="button button-primary"
        type="button"
        disabled={$isLoading}
        on:click={handleNext}
      >
        {isLastStep ? "完了" : "次へ"}
        <ChevronRight class="button-icon" size={20} />
      </button>
    </div>
  </div>
</div>

<ErrorDialog
  bind:open={showErrorDialog}
  error={$error}
  onClose={handleErrorClose}
  onRetry={handleErrorRetry}
/>

<ConfirmDialog
  bind:open={showSkipConfirm}
  title="ステップをスキップ"
  message="このステップをスキップしますか？後で設定することもできます。"
  confirmText="スキップする"
  cancelText="キャンセル"
  variant="warning"
  onConfirm={handleSkipConfirm}
/>

<CompletionDialog
  bind:open={showCompletionDialog}
  onContinue={handleCompletionContinue}
/>

<style>
  .installer-wizard {
    width: 100%;
    max-width: 900px;
    margin: 2rem auto;
    padding: 2rem;
    display: flex;
    flex-direction: column;
    min-height: 600px;
  }

  .wizard-header {
    text-align: left;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--divider-color);
  }

  .wizard-title {
    margin: 0 0 0.5rem 0;
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent-color);
  }

  .wizard-subtitle {
    margin: 0;
    font-size: 1rem;
    color: var(--text-secondary);
  }

  .wizard-progress {
    width: 100%;
  }

  .wizard-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 400px;
  }

  .step-container {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .loading-container,
  .error-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
  }

  .loading-spinner {
    width: 48px;
    height: 48px;
    border: 4px solid rgba(255, 255, 255, 0.1);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .loading-text,
  .error-text {
    margin: 0;
    font-size: 1rem;
    color: var(--text-secondary);
  }

  .placeholder-content {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    background: rgba(0, 0, 0, 0.2);
    border: 2px dashed rgba(255, 255, 255, 0.1);
    border-radius: 12px;
  }

  .placeholder-content p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 1rem;
  }

  .wizard-footer {
    padding-top: 1.5rem;
    border-top: 1px solid var(--divider-color);
  }

  .footer-actions {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .footer-spacer {
    flex: 1;
  }

  .button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    white-space: nowrap;
  }

  .button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
  }

  .button-primary {
    background: linear-gradient(
      135deg,
      var(--accent-color) 0%,
      var(--accent-color-strong) 100%
    );
    color: white;
    border-color: var(--accent-color);
  }

  .button-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px var(--accent-glow);
  }

  .button-secondary {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .button-secondary:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-2px);
  }

  .button-skip {
    background: rgba(255, 165, 0, 0.1);
    color: #ffa500;
    border-color: rgba(255, 165, 0, 0.3);
  }

  .button-skip:hover:not(:disabled) {
    background: rgba(255, 165, 0, 0.2);
    border-color: rgba(255, 165, 0, 0.5);
    transform: translateY(-2px);
  }

  .button-icon {
    display: block;
    flex-shrink: 0;
  }

  @media (max-width: 768px) {
    .installer-wizard {
      margin: 1rem;
      padding: 1.5rem;
    }

    .wizard-title {
      font-size: 1.5rem;
    }

    .wizard-subtitle {
      font-size: 0.875rem;
    }

    .footer-actions {
      flex-wrap: wrap;
    }

    .button {
      padding: 0.625rem 1.25rem;
      font-size: 0.9375rem;
    }
  }
</style>
