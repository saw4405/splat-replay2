<script lang="ts">
  import { onMount } from 'svelte';
  import type { ComponentType } from 'svelte';
  import { ChevronLeft, ChevronRight } from 'lucide-svelte';
  import {
    setupState,
    isLoading,
    error,
    progressInfo,
    fetchInstallationStatus,
    clearError,
    completeInstallation,
  } from '../stores/state';
  import {
    goToNextStep,
    goToPreviousStep,
    skipCurrentStep,
    executeStep,
  } from '../stores/navigation';
  import { SetupStep } from '../types';
  import ErrorDialog from '../../common/components/ErrorDialog.svelte';
  import NotificationDialog from '../../common/components/NotificationDialog.svelte';

  // ステップコンポーネントのスロット
  export let currentStepComponent: ComponentType | null = null;

  // 現在のステップコンポーネントのインスタンス
  let stepComponentInstance: unknown;

  // 子コンポーネントが戻れるかどうか
  let childCanGoBack = false;
  let childAtFinalSubstep = false;
  let childStepCompleted = false;
  let shouldShowCompletion = false;
  let lastObservedStep: SetupStep | null = null;

  let showErrorDialog = false;
  let showCompletionDialog = false;
  let showWarningDialog = false;
  let hasIncompleteTasksMessage = '';
  let isAllTasksCompleted = true;

  $: if ($error) {
    showErrorDialog = true;
  }

  $: canGoBack = $setupState ? $setupState.current_step !== SetupStep.HARDWARE_CHECK : false;

  $: isLastStep = $setupState ? $setupState.current_step === SetupStep.YOUTUBE_SETUP : false;

  $: {
    const currentStep = $setupState?.current_step ?? null;
    if (currentStep !== lastObservedStep) {
      childAtFinalSubstep = false;
      lastObservedStep = currentStep;
    }
  }

  $: shouldShowCompletion = isLastStep && childAtFinalSubstep;

  $: {
    console.log('[SetupWizard] State update', {
      isLastStep,
      childAtFinalSubstep,
      shouldShowCompletion,
      childStepCompleted,
      showCompletionDialog,
    });
  }

  // 最後のステップの最後のサブステップに到達したら、次へボタンを押した時に完了処理を実行する
  $: if (shouldShowCompletion && !showCompletionDialog) {
    // フラグのみ設定し、実際の完了処理はhandleNext()で行う
  }

  /**
   * すべてのタスクが完了しているかチェック
   * すべてのステップのすべてのタスクが完了している必要がある
   */
  function checkAllTasksCompleted(): boolean {
    if (!$setupState) return false;

    const { step_details, current_step, skipped_steps } = $setupState;
    const incompleteSteps: string[] = [];

    // すべてのステップをチェック
    const allSteps = [
      SetupStep.HARDWARE_CHECK,
      SetupStep.FFMPEG_SETUP,
      SetupStep.OBS_SETUP,
      SetupStep.TESSERACT_SETUP,
      SetupStep.FONT_INSTALLATION,
      SetupStep.TRANSCRIPTION_SETUP,
      SetupStep.YOUTUBE_SETUP,
    ];

    for (const step of allSteps) {
      // まだ到達していないステップは除外
      const currentStepIndex = allSteps.indexOf(current_step);
      const stepIndex = allSteps.indexOf(step);
      if (stepIndex > currentStepIndex) {
        continue;
      }

      const details = step_details[step] || {};
      const incompleteTasks = Object.entries(details)
        .filter(([_key, completed]) => !completed)
        .map(([key]) => key);

      // タスクが存在しない、または一部でも未完了の場合
      if (Object.keys(details).length === 0 || incompleteTasks.length > 0) {
        // スキップされたステップかチェック
        if (skipped_steps.includes(step)) {
          incompleteSteps.push(`${step}: スキップされています`);
        } else {
          incompleteSteps.push(`${step}: ${incompleteTasks.join(', ')}`);
        }
      }
    }

    if (incompleteSteps.length > 0) {
      hasIncompleteTasksMessage =
        '以下のステップ・タスクが完了していません：\n\n' + incompleteSteps.join('\n');
      return false;
    }

    return true;
  }

  onMount(async () => {
    await fetchInstallationStatus();
  });

  async function handleNext(): Promise<void> {
    // コンポーネント側で次へ処理が実装されている場合はそれを優先
    const instance = stepComponentInstance as {
      next?: (opts: { skip: boolean }) => Promise<boolean>;
    };
    if (stepComponentInstance && instance.next) {
      const isSkipping = !childStepCompleted;
      const handled = await instance.next({ skip: isSkipping });
      if (handled) return;

      // 最後のステップで完了ダイアログを表示
      if (isLastStep) {
        if (isSkipping) {
          await skipCurrentStep();
        }
        // すべてのタスクが完了しているかチェック
        isAllTasksCompleted = checkAllTasksCompleted();
        if (isAllTasksCompleted) {
          showCompletionDialog = true;
        } else {
          showWarningDialog = true;
        }
        return;
      }

      // スキップしている場合はステップ全体をスキップとしてマーク
      if (isSkipping) {
        await skipCurrentStep();
        await goToNextStep();
        return;
      }
    }

    // 現在のステップを完了としてマークしてから次へ進む
    if ($setupState) {
      try {
        await executeStep($setupState.current_step);
      } catch (err) {
        // エラーは既にストアで処理されているので、ここでは何もしない
        console.error('Failed to complete step:', err);
        return;
      }

      // 最後のステップの場合は完了ダイアログを表示
      if (isLastStep) {
        isAllTasksCompleted = checkAllTasksCompleted();
        if (isAllTasksCompleted) {
          showCompletionDialog = true;
        } else {
          showWarningDialog = true;
        }
        return;
      }
    }
    await goToNextStep();
  }

  async function handleBack(): Promise<void> {
    // コンポーネント側で戻る処理が実装されている場合はそれを優先
    const instance = stepComponentInstance as { back?: () => Promise<boolean> };
    if (stepComponentInstance && instance.back) {
      const handled = await instance.back();
      if (handled) return;
    }

    await goToPreviousStep();
  }

  function handleSubstepChange(event: CustomEvent<{ isFinalSubstep: boolean }>): void {
    childAtFinalSubstep = event.detail.isFinalSubstep;
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

  async function handleCompletionContinue(): Promise<void> {
    // インストール完了状態を保存してからページをリロードしてメインアプリに遷移
    await completeInstallation();
    window.location.reload();
  }

  function handleWarningClose(): void {
    showWarningDialog = false;
  }
</script>

<div class="setup-wizard glass-surface">
  <div class="wizard-header">
    <h1 class="wizard-title">Splat Replay セットアップ</h1>
    {#if $progressInfo}
      <div class="progress-container">
        <div class="progress-info">
          <div class="progress-step-info">
            <span class="progress-step"
              >ステップ {$progressInfo.current_step_index + 1} / {$progressInfo.total_steps}</span
            >
            <span class="progress-substep"
              >タスク {$progressInfo.completed_substeps} / {$progressInfo.total_substeps}</span
            >
          </div>
          <span class="progress-percentage">{$progressInfo.percentage}%</span>
        </div>
        <div class="progress-bar-wrapper">
          <div class="progress-bar" style="width: {$progressInfo.percentage}%"></div>
        </div>
      </div>
    {/if}
  </div>

  <div class="wizard-content">
    {#if $isLoading && !$setupState}
      <div class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">読み込み中...</p>
      </div>
    {:else if $setupState}
      <div class="step-container">
        <div class="step-wrapper">
          <slot name="step-content">
            {#if currentStepComponent}
              <svelte:component
                this={currentStepComponent}
                bind:this={stepComponentInstance}
                bind:canGoBack={childCanGoBack}
                bind:isStepCompleted={childStepCompleted}
                on:substepChange={handleSubstepChange}
              />
            {:else}
              <div class="placeholder-content">
                <p>ステップコンテンツがありません</p>
              </div>
            {/if}
          </slot>
        </div>
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
        disabled={(!canGoBack && !childCanGoBack) || $isLoading}
        on:click={handleBack}
      >
        <ChevronLeft class="button-icon" size={20} />
        戻る
      </button>

      <div class="footer-spacer"></div>

      <button
        class="button button-primary"
        class:button-skip={!shouldShowCompletion && !childStepCompleted}
        type="button"
        disabled={$isLoading}
        on:click={handleNext}
      >
        {shouldShowCompletion ? '完了' : childStepCompleted ? '次へ' : 'スキップ'}
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

<NotificationDialog
  bind:isOpen={showCompletionDialog}
  variant="success"
  title="セットアップ完了！"
  message="Splat Replay のセットアップが完了しました。"
  buttonText="アプリケーションを開始"
  on:close={handleCompletionContinue}
/>

<NotificationDialog
  bind:isOpen={showWarningDialog}
  variant="warning"
  title="未完了のタスクがあります"
  message={hasIncompleteTasksMessage +
    '\n\nセットアップを完了させるには、すべてのタスクを完了してください。'}
  buttonText="閉じる"
  on:close={handleWarningClose}
/>

<style>
  .setup-wizard {
    width: 100%;
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    max-height: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
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

  .progress-container {
    margin-top: 1rem;
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .progress-step-info {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 1rem;
  }

  .progress-step {
    font-weight: 500;
  }

  .progress-substep {
    font-size: 0.8125rem;
    opacity: 0.75;
  }

  .progress-percentage {
    font-weight: 600;
    color: var(--accent-color);
    font-size: 1.125rem;
  }

  .progress-bar-wrapper {
    width: 100%;
    height: 8px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    overflow: hidden;
    position: relative;
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    border-radius: 4px;
    transition: width 0.3s ease;
    position: relative;
  }

  .progress-bar::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.3) 50%,
      transparent 100%
    );
    animation: shimmer 2s infinite;
  }

  @keyframes shimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }

  .wizard-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0; /* Important for nested flex scrolling */
    overflow: hidden; /* Don't scroll here, let child handle it */
    padding-bottom: 1rem;
  }

  .step-container {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .step-wrapper {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  :global(.step-wrapper > *) {
    flex: 1;
    min-height: 0;
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
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    color: white;
    border-color: var(--accent-color);
  }

  .button-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px var(--accent-glow);
  }

  .button-skip {
    background: linear-gradient(
      135deg,
      rgba(255, 159, 10, 0.9) 0%,
      rgba(255, 149, 0, 0.9) 100%
    ) !important;
    color: white !important;
    border-color: rgba(255, 159, 10, 0.8) !important;
  }

  .button-skip:hover:not(:disabled) {
    background: linear-gradient(
      135deg,
      rgba(255, 159, 10, 1) 0%,
      rgba(255, 149, 0, 1) 100%
    ) !important;
    border-color: rgba(255, 159, 10, 1) !important;
    box-shadow: 0 6px 16px rgba(255, 159, 10, 0.4) !important;
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

  @media (max-width: 768px) {
    .setup-wizard {
      margin: 1rem;
      padding: 1.5rem;
    }

    .wizard-title {
      font-size: 1.5rem;
    }

    .footer-actions {
      flex-wrap: wrap;
    }

    .button {
      padding: 0.625rem 1.25rem;
      font-size: 0.9375rem;
    }
  }

  @media (max-height: 700px) {
    .setup-wizard {
      padding: 1rem;
    }

    .wizard-header {
      padding-bottom: 0.5rem;
    }

    .wizard-title {
      font-size: 1.5rem;
      margin-bottom: 0.25rem;
    }

    .wizard-footer {
      padding-top: 0.75rem;
    }

    .button {
      padding: 0.5rem 1rem;
    }
  }
</style>
