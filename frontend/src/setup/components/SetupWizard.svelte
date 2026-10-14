<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import type { Component } from 'svelte';
  import { ChevronLeft, ChevronRight } from 'lucide-svelte';
  import {
    setupState,
    isLoading,
    error,
    progressInfo,
    API_BASE_URL,
    fetchInstallationStatus,
    clearError,
    completeInstallation,
    handleApiError,
    isRequiredSetupIssue,
    safeParseJson,
  } from '../stores/state';
  import {
    getRequiredIssueSubstepStorageKey,
    isRequiredIssueSubstepSupported,
    setRequiredIssueSubstep,
  } from '../stores/navigation';
  import {
    goToNextStep,
    goToPreviousStep,
    skipCurrentStep,
    executeStep,
  } from '../stores/navigation';
  import { SetupStep, type RequiredSetupIssue } from '../types';
  import ErrorDialog from '../../common/components/ErrorDialog.svelte';

  interface Props {
    currentStepComponent?: Component | null;
  }

  let { currentStepComponent = null }: Props = $props();

  // 現在のステップコンポーネントのインスタンス
  let stepComponentInstance = $state<unknown>(undefined);

  // 子コンポーネントが戻れるかどうか
  let childCanGoBack = $state(false);
  let childAtFinalSubstep = $state(false);
  let childStepCompleted = $state(false);
  let shouldShowCompletion = $state(false);
  let lastObservedStep = $state<SetupStep | null>(null);
  let selectedIssue = $state<RequiredSetupIssue | null>(null);
  let hasTriedCompletion = $state(false);
  let repairVersion = $state(0);
  let isRepairing = $state(false);

  let showErrorDialog = $state(false);

  const orderedSteps = [
    SetupStep.HARDWARE_CHECK,
    SetupStep.FFMPEG_SETUP,
    SetupStep.OBS_SETUP,
    SetupStep.TESSERACT_SETUP,
    SetupStep.FONT_INSTALLATION,
    SetupStep.TRANSCRIPTION_SETUP,
    SetupStep.YOUTUBE_SETUP,
  ];

  $effect(() => {
    if ($error) {
      showErrorDialog = true;
    }
  });

  const canGoBack = $derived(
    $setupState ? $setupState.current_step !== SetupStep.HARDWARE_CHECK : false
  );

  const isLastStep = $derived(
    $setupState ? $setupState.current_step === SetupStep.YOUTUBE_SETUP : false
  );
  const showRequiredIssues = $derived(
    Boolean(
      $setupState &&
      $setupState.required_setup_issues.length > 0 &&
      ($setupState.is_completed || hasTriedCompletion) &&
      !selectedIssue
    )
  );

  $effect(() => {
    const currentStep = $setupState?.current_step ?? null;
    if (currentStep !== lastObservedStep) {
      childAtFinalSubstep = false;
      lastObservedStep = currentStep;
    }
  });

  $effect(() => {
    shouldShowCompletion = isLastStep && childAtFinalSubstep;
  });

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

      // 最後のステップはサーバーで必須設定を再確認して完了する
      if (isLastStep) {
        await validateAndCompleteSetup();
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

      // 最後のステップはサーバーで必須設定を再確認して完了する
      if (isLastStep) {
        await validateAndCompleteSetup();
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

  function handleSubstepChange(isFinalSubstep: boolean): void {
    childAtFinalSubstep = isFinalSubstep;
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

  async function validateAndCompleteSetup(): Promise<void> {
    hasTriedCompletion = true;
    try {
      await completeInstallation();
    } catch (err) {
      const hasIssues = (get(setupState)?.required_setup_issues.length ?? 0) > 0;
      if (hasIssues) {
        selectedIssue = null;
      }
      if (!get(error)?.error || !hasJapaneseText(get(error)?.error ?? '')) {
        error.set({
          error: hasIssues
            ? '必須設定の不足を確認してください。表示された項目を修復してください。'
            : japaneseErrorMessage(
                err,
                'セットアップの完了確認に失敗しました。通信状況を確認して再試行してください。'
              ),
        });
      }
    }
  }

  async function openRequiredIssue(issue: RequiredSetupIssue): Promise<void> {
    if (isRepairing) return;
    const storageKey = getRequiredIssueSubstepStorageKey(issue);
    if (!storageKey || !isRequiredIssueSubstepSupported(issue)) {
      error.set({
        error: 'この必須項目の修復画面を開けませんでした。セットアップを再読み込みしてください。',
      });
      return;
    }

    isRepairing = true;
    const previousSubstepIndex = window.sessionStorage.getItem(storageKey);
    let failureMessage = '修復画面を開けませんでした。必須設定の状態を確認してください。';
    try {
      const response = await fetch(
        `${API_BASE_URL}/setup/repair/${encodeURIComponent(issue.code)}`,
        { method: 'POST' }
      );
      if (!response.ok) await handleApiError(response);

      const target = await safeParseJson<unknown>(response);
      if (
        !isRequiredSetupIssue(target) ||
        target.code !== issue.code ||
        !isRequiredIssueSubstepSupported(target) ||
        !setRequiredIssueSubstep(target)
      ) {
        throw new Error('修復先の情報を読み取れませんでした。もう一度お試しください。');
      }

      await fetchInstallationStatus({ refresh: true, throwOnError: true });
      const state = get(setupState);
      if (!state || state.current_step !== target.step) {
        throw new Error('修復状態を再確認できませんでした。必須設定の一覧を更新してください。');
      }

      selectedIssue = target;
      repairVersion += 1;
    } catch (err) {
      failureMessage = japaneseErrorMessage(
        err,
        '修復に失敗しました。通信状況を確認して再試行してください。'
      );
      if (previousSubstepIndex === null) {
        window.sessionStorage.removeItem(storageKey);
      } else {
        window.sessionStorage.setItem(storageKey, previousSubstepIndex);
      }
      selectedIssue = null;

      try {
        await fetchInstallationStatus({ refresh: true, throwOnError: true });
      } catch {
        failureMessage =
          '必須設定の一覧を更新できませんでした。通信状況を確認して再試行してください。';
      }
      error.set({ error: failureMessage });
    } finally {
      isRepairing = false;
    }
  }

  async function returnToRequiredIssues(): Promise<void> {
    if (get(isLoading)) return;

    try {
      await fetchInstallationStatus({ refresh: true, throwOnError: true });
      selectedIssue = null;
    } catch (err) {
      error.set({
        error: japaneseErrorMessage(
          err,
          '必須設定の再検査に失敗しました。通信状況を確認して再試行してください。'
        ),
      });
    }
  }

  function canOpenRequiredIssue(issue: RequiredSetupIssue): boolean {
    return orderedSteps.includes(issue.step) && isRequiredIssueSubstepSupported(issue);
  }

  function hasJapaneseText(message: string): boolean {
    return /[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}]/u.test(message);
  }

  function japaneseErrorMessage(err: unknown, fallback: string): string {
    return err instanceof Error && hasJapaneseText(err.message) ? err.message : fallback;
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
      {#if showRequiredIssues}
        <section class="required-issues" aria-labelledby="required-issues-title" role="alert">
          <h2 id="required-issues-title">起動に必要な設定が不足しています</h2>
          <p>以下の項目を修復してください。</p>
          <ul>
            {#each $setupState.required_setup_issues as issue (issue.code)}
              <li>
                <span>{issue.message}</span>
                <button
                  class="button button-secondary"
                  type="button"
                  disabled={!canOpenRequiredIssue(issue) || $isLoading || isRepairing}
                  onclick={() => openRequiredIssue(issue)}
                >
                  修復する
                </button>
                {#if !canOpenRequiredIssue(issue)}
                  <small>修復画面を開けません。セットアップを再読み込みしてください。</small>
                {/if}
              </li>
            {/each}
          </ul>
        </section>
      {:else}
        {#if $setupState.required_setup_issues.length > 0}
          <button
            class="button button-secondary repair-list-button"
            type="button"
            disabled={$isLoading}
            onclick={returnToRequiredIssues}
          >
            再検査して不足一覧へ戻る
          </button>
        {/if}
        <div class="step-container">
          <div class="step-wrapper">
            {#if currentStepComponent}
              {#key repairVersion}
                {@const StepComp = currentStepComponent as unknown as import('svelte').Component}
                <StepComp
                  bind:this={stepComponentInstance}
                  bind:canGoBack={childCanGoBack}
                  bind:isStepCompleted={childStepCompleted}
                  onSubstepChange={handleSubstepChange}
                />
              {/key}
            {:else}
              <div class="placeholder-content">
                <p>ステップコンテンツがありません</p>
              </div>
            {/if}
          </div>
        </div>
      {/if}
    {:else}
      <div class="error-container">
        <p class="error-text">インストール状態を読み込めませんでした</p>
      </div>
    {/if}
  </div>

  {#if !showRequiredIssues}
    <div class="wizard-footer">
      <div class="footer-actions">
        <button
          class="button button-secondary"
          type="button"
          disabled={(!canGoBack && !childCanGoBack) || $isLoading}
          onclick={handleBack}
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
          onclick={handleNext}
        >
          {shouldShowCompletion ? '完了' : childStepCompleted ? '次へ' : 'スキップ'}
          <ChevronRight class="button-icon" size={20} />
        </button>
      </div>
    </div>
  {/if}
</div>

<ErrorDialog
  bind:open={showErrorDialog}
  error={$error}
  onClose={handleErrorClose}
  onRetry={handleErrorRetry}
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

  .required-issues {
    display: flex;
    flex: 1;
    min-height: 0;
    flex-direction: column;
    gap: 0.75rem;
    overflow-y: auto;
    padding: 1rem 0;
  }

  .required-issues h2,
  .required-issues p {
    margin: 0;
  }

  .required-issues h2 {
    color: var(--accent-color);
    font-size: 1.25rem;
  }

  .required-issues ul {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .required-issues li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.5rem 1rem;
    padding: 0.75rem;
    border: 1px solid var(--divider-color);
    border-radius: 0.75rem;
    background: var(--glass-bg);
  }

  .required-issues small {
    grid-column: 1 / -1;
    color: var(--text-secondary);
  }

  .repair-list-button {
    align-self: flex-start;
    margin-bottom: 0.75rem;
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
    background: rgba(var(--theme-rgb-white), 0.1);
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
      rgba(var(--theme-rgb-white), 0.3) 50%,
      transparent 100%
    );
    opacity: 0.45;
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
    border: 4px solid rgba(var(--theme-rgb-white), 0.1);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    box-shadow: 0 0 12px rgba(var(--theme-rgb-accent), 0.12);
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
    background: rgba(var(--theme-rgb-black), 0.2);
    border: 2px dashed rgba(var(--theme-rgb-white), 0.1);
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
    transition:
      background 0.2s ease,
      border-color 0.2s ease,
      box-shadow 0.2s ease,
      color 0.2s ease;
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
    color: var(--theme-color-white);
    border-color: var(--accent-color);
  }

  .button-primary:hover:not(:disabled) {
    box-shadow: 0 4px 10px rgba(var(--theme-rgb-accent), 0.2);
  }

  .button-skip {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-orange-soft), 0.9) 0%,
      rgba(var(--theme-rgb-orange), 0.9) 100%
    ) !important;
    color: var(--theme-color-white) !important;
    border-color: rgba(var(--theme-rgb-orange-soft), 0.8) !important;
  }

  .button-skip:hover:not(:disabled) {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-orange-soft), 1) 0%,
      rgba(var(--theme-rgb-orange), 1) 100%
    ) !important;
    border-color: rgba(var(--theme-rgb-orange-soft), 1) !important;
    box-shadow: 0 4px 10px rgba(var(--theme-rgb-orange-soft), 0.24) !important;
  }

  .button-secondary {
    background: rgba(var(--theme-rgb-white), 0.05);
    color: var(--text-primary);
    border-color: rgba(var(--theme-rgb-white), 0.1);
  }

  .button-secondary:hover:not(:disabled) {
    background: rgba(var(--theme-rgb-white), 0.1);
    border-color: rgba(var(--theme-rgb-white), 0.2);
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
