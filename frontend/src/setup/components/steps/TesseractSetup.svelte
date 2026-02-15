<script lang="ts">
  import { onMount } from 'svelte';
  import { Download, ExternalLink, FolderOpen, Check } from 'lucide-svelte';
  import { checkSystem, setupTesseract } from '../../stores/system';
  import { markSubstepCompleted } from '../../stores/navigation';
  import { setupState } from '../../stores/state';
  import { type SystemCheckResult, SetupStep } from '../../types';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';

  const SUBSTEP_STORAGE_KEY = 'tesseract_substep_index';

  interface SetupStep {
    id: string;
    title: string;
    description: string;
    completed: boolean;
  }

  let tesseractInstalled = false;
  let _tesseractVersion: string | null = null;
  let isChecking = false;
  let hasInitializedSubstep = false;
  let dialogOpen = false;
  let dialogMessage = '';
  let dialogVariant: 'info' | 'success' | 'warning' | 'error' = 'info';

  let setupSteps: SetupStep[] = [
    {
      id: 'tesseract-install',
      title: 'Tesseractのインストール',
      description: '文字認識機能を使用するため、Tesseract OCR をインストールします。',
      completed: false,
    },
    {
      id: 'tesseract-lang-data',
      title: '追加データの配置',
      description: 'Tesseract OCR の追加言語データをダウンロードして配置します。',
      completed: false,
    },
  ];

  let currentSubStepIndex = 0;

  // 親コンポーネントに通知するためのフラグ
  export let canGoBack = false;
  export let isStepCompleted = false;

  $: isStepCompleted = setupSteps[currentSubStepIndex].completed;

  $: canGoBack = currentSubStepIndex > 0;

  onMount(async () => {
    await checkTesseractInstallation();
  });

  function loadSavedSubstepIndex(maxIndex: number): number | null {
    if (typeof window === 'undefined') return null;
    const stored = window.sessionStorage.getItem(SUBSTEP_STORAGE_KEY);
    if (stored === null) return null;
    const parsed = Number.parseInt(stored, 10);
    if (Number.isNaN(parsed)) return null;
    return Math.max(0, Math.min(parsed, maxIndex));
  }

  function saveSubstepIndex(index: number): void {
    if (typeof window === 'undefined') return;
    window.sessionStorage.setItem(SUBSTEP_STORAGE_KEY, index.toString());
  }

  function computeInitialSubstepIndex(_steps: SetupStep[]): number {
    // 常に最初の手順から開始する
    return 0;
  }

  // 現在のステップが変更されたときにhasInitializedSubstepをリセット
  $: if ($setupState?.current_step !== SetupStep.TESSERACT_SETUP) {
    hasInitializedSubstep = false;
  }

  // Sync with installation state
  $: if ($setupState && $setupState.step_details) {
    const details = $setupState.step_details[SetupStep.TESSERACT_SETUP] || {};
    const updatedSteps = setupSteps.map((step) => ({
      ...step,
      completed: details[step.id] || false,
    }));
    setupSteps = updatedSteps;

    if (!hasInitializedSubstep && $setupState.current_step === SetupStep.TESSERACT_SETUP) {
      const savedIndex = loadSavedSubstepIndex(updatedSteps.length - 1);
      if (savedIndex !== null) {
        currentSubStepIndex = savedIndex;
      } else {
        currentSubStepIndex = computeInitialSubstepIndex(updatedSteps);
      }
      hasInitializedSubstep = true;
    }
  }

  $: if (hasInitializedSubstep) {
    saveSubstepIndex(currentSubStepIndex);
  }

  export async function next(options: { skip?: boolean } = {}): Promise<boolean> {
    const currentStep = setupSteps[currentSubStepIndex];

    // インストールチェックが必要なステップのバリデーション
    if (currentSubStepIndex === 0 && !tesseractInstalled) {
      await checkTesseractInstallation();
      if (!tesseractInstalled) {
        showDialog(
          'Tesseract が検出されませんでした。インストールしてから次へ進んでください。',
          'warning'
        );
        return true;
      }
    }

    if (!options.skip && !currentStep.completed) {
      await markSubstepCompleted(SetupStep.TESSERACT_SETUP, currentStep.id, true);
    }

    if (currentSubStepIndex < setupSteps.length - 1) {
      currentSubStepIndex++;
      return true;
    }
    return false;
  }

  export async function back(): Promise<boolean> {
    if (currentSubStepIndex > 0) {
      currentSubStepIndex--;
      return true;
    }
    return false;
  }

  async function checkTesseractInstallation(): Promise<void> {
    isChecking = true;

    try {
      const result: SystemCheckResult = await checkSystem('tesseract');
      tesseractInstalled = result.is_installed;
      _tesseractVersion = result.version || null;

      if (tesseractInstalled) {
        await markSubstepCompleted(SetupStep.TESSERACT_SETUP, 'tesseract-install', true);
      }
    } catch (error) {
      console.error('Tesseract check failed', error);
    } finally {
      isChecking = false;
    }
  }

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    // インストール済みならチェックを外せないようにする
    if (index === 0 && tesseractInstalled) return;

    if (index === 0 && !step.completed) {
      // Check installation when user clicks checkbox for install step
      isChecking = true;

      try {
        const result = await setupTesseract();

        if (result.is_installed) {
          tesseractInstalled = true;
          _tesseractVersion = result.version || null;
          await markSubstepCompleted(SetupStep.TESSERACT_SETUP, step.id, true);
        } else {
          showDialog('Tesseract が検出されませんでした。', 'warning');
        }
      } catch (error) {
        console.error('Tesseract setup failed', error);
        showDialog('Tesseract のセットアップに失敗しました。', 'error');
      } finally {
        isChecking = false;
      }
    } else {
      await markSubstepCompleted(SetupStep.TESSERACT_SETUP, step.id, !step.completed);
    }
  }

  function handleCardClick(event: Event) {
    // テキスト選択中は反応しない
    if (window.getSelection()?.toString()) {
      return;
    }

    // イベントターゲットの取得と要素への正規化（テキストノードの場合は親要素を取得）
    let target = event.target as Element;
    if (target.nodeType === Node.TEXT_NODE) {
      target = target.parentElement as Element;
    }

    // インタラクティブな要素のクリックは除外
    if (
      target &&
      (target.closest('button') ||
        target.closest('a') ||
        target.closest('input') ||
        target.closest('.path-value'))
    ) {
      return;
    }

    toggleStep(currentSubStepIndex);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      handleCardClick(event);
    }
  }

  function openUrl(url: string): void {
    window.open(url, '_blank');
  }

  function showDialog(
    message: string,
    variant: 'info' | 'success' | 'warning' | 'error' = 'info'
  ): void {
    dialogMessage = message;
    dialogVariant = variant;
    dialogOpen = true;
  }
</script>

<div class="tesseract-setup">
  <div class="step-header">
    <h2 class="step-title">Tesseract OCR セットアップ</h2>
    <p class="step-description">文字認識機能を使用するため、Tesseract OCR をインストールします</p>
  </div>

  <div class="setup-steps-section">
    <div
      class="step-card glass-card"
      class:completed={setupSteps[currentSubStepIndex].completed}
      class:disabled={(currentSubStepIndex === 0 && tesseractInstalled) ||
        (currentSubStepIndex === 0 && isChecking)}
      on:click={handleCardClick}
      on:keydown={handleKeyDown}
      role="button"
      tabindex="0"
    >
      {#key currentSubStepIndex}
        <div class="step-content-wrapper">
          <div class="card-header">
            <div class="header-left">
              <div class="step-number-large">{currentSubStepIndex + 1}</div>
              <div class="title-wrapper">
                <h3 class="step-name-large">
                  {setupSteps[currentSubStepIndex].title}
                </h3>
                {#if currentSubStepIndex === 0 && tesseractInstalled}
                  <span class="installed-badge">インストール済</span>
                {/if}
              </div>
            </div>
            <div
              class="checkbox-indicator"
              class:checked={setupSteps[currentSubStepIndex].completed}
            >
              {#if setupSteps[currentSubStepIndex].completed}
                <Check size={20} />
              {/if}
            </div>
          </div>

          <div class="card-body">
            {#if currentSubStepIndex === 0}
              <!-- Tesseract Install -->
              <ol class="instruction-list">
                <li>
                  下のボタンからダウンロードページを開き、「tesseract-ocr-w64-setup-*.exe」をダウンロードします
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() => openUrl('https://github.com/UB-Mannheim/tesseract/wiki')}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>インストーラーを実行してインストールします</li>
              </ol>
              <p class="step-note">
                ※ インストール後、右のチェックボックスをオンにすると、自動的に環境変数 PATH
                の設定とインストール確認が行われます。
              </p>
            {:else if currentSubStepIndex === 1}
              <!-- Language Data -->
              <ol class="instruction-list">
                <li>
                  下のボタンからデータ配布ページを開き、<span class="inline-icon-wrapper"
                    ><Download class="inline-icon" size={16} /></span
                  >(Download raw file)ボタンをクリックしてダウンロードします
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          'https://github.com/tesseract-ocr/tessdata_best/blob/main/eng.traineddata'
                        )}
                    >
                      <Download class="icon" size={16} />
                      eng.traineddata をダウンロード
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>
                  ダウンロードしたファイルを以下のフォルダに上書き保存します<br />
                  <div class="path-box">
                    <FolderOpen class="icon" size={20} />
                    <div class="path-content">
                      <code class="path-value"> C:\Program Files\Tesseract-OCR\tessdata </code>
                      <p class="path-hint">※ ファイル名: eng.traineddata</p>
                    </div>
                  </div>
                </li>
              </ol>
            {/if}
          </div>
        </div>
      {/key}
    </div>
  </div>

  <NotificationDialog
    isOpen={dialogOpen}
    variant={dialogVariant}
    message={dialogMessage}
    on:close={() => (dialogOpen = false)}
  />
</div>

<style>
  .tesseract-setup {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 0;
    height: 100%;
    justify-content: center;
  }

  .step-header {
    text-align: center;
    margin-bottom: 1rem;
  }

  .step-title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .step-description {
    margin: 0.5rem 0 0 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }

  .setup-steps-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 0;
  }

  .step-card {
    width: 100%;
    max-width: 600px;
    height: 100%;
    padding: 2rem;
    display: flex;
    flex-direction: column;
    background: rgba(var(--theme-rgb-white), 0.03);
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
    border-radius: 16px;
    max-height: 100%;
    box-sizing: border-box;
    cursor: pointer;
    transition: all 0.2s ease;
    outline: none;
  }

  .step-card:focus-visible {
    box-shadow: 0 0 0 2px var(--accent-color);
  }

  .step-card:hover {
    border-color: rgba(var(--theme-rgb-white), 0.3);
    background: rgba(var(--theme-rgb-white), 0.05);
  }

  .step-card.completed {
    border-color: var(--accent-color);
    box-shadow: 0 0 15px rgba(var(--theme-rgb-accent), 0.1);
    background: rgba(var(--theme-rgb-accent), 0.05);
  }

  .step-card.disabled {
    cursor: default;
    opacity: 0.8;
  }

  .step-card.disabled:hover {
    border-color: rgba(var(--theme-rgb-white), 0.1);
    background: rgba(var(--theme-rgb-white), 0.03);
  }

  .step-content-wrapper {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    width: 100%;
    animation: fadeIn 0.3s ease-out;
    overflow: hidden;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid rgba(var(--theme-rgb-white), 0.1);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .checkbox-indicator {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: 2px solid rgba(var(--theme-rgb-white), 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: transparent;
    transition: all 0.2s ease;
    background: rgba(var(--theme-rgb-white), 0.05);
  }

  .checkbox-indicator.checked {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: var(--theme-color-charcoal);
    box-shadow: 0 0 10px var(--accent-glow);
  }

  .step-card:hover .checkbox-indicator:not(.checked) {
    border-color: rgba(var(--theme-rgb-white), 0.4);
    background: rgba(var(--theme-rgb-white), 0.1);
  }

  .step-number-large {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.2) 0%,
      rgba(var(--theme-rgb-accent), 0.05) 100%
    );
    border: 2px solid rgba(var(--theme-rgb-accent), 0.3);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent-color);
    flex-shrink: 0;
  }

  .title-wrapper {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }

  .step-name-large {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-primary);
    text-align: left;
  }

  .card-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    text-align: left;
    overflow-y: auto;
    flex: 1;
    min-height: 0; /* Allow shrinking for scroll */
    padding-right: 0.5rem;
    box-sizing: border-box;
  }

  .card-body::-webkit-scrollbar {
    width: 8px;
  }

  .card-body::-webkit-scrollbar-track {
    background: rgba(var(--theme-rgb-white), 0.05);
    border-radius: 4px;
  }

  .card-body::-webkit-scrollbar-thumb {
    background: rgba(var(--theme-rgb-white), 0.2);
    border-radius: 4px;
  }

  .card-body::-webkit-scrollbar-thumb:hover {
    background: rgba(var(--theme-rgb-white), 0.3);
  }

  .installed-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    color: var(--theme-color-white);
    box-shadow: 0 0 8px var(--accent-glow);
  }

  .step-note {
    margin: 1rem 0 0 0;
    font-size: 0.85rem;
    font-style: italic;
    color: var(--text-secondary);
  }

  .link-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 6px;
    border: 1px solid rgba(var(--theme-rgb-white), 0.2);
    background: rgba(var(--theme-rgb-white), 0.05);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .link-button:hover {
    background: rgba(var(--theme-rgb-white), 0.1);
    border-color: rgba(var(--theme-rgb-white), 0.3);
    transform: translateY(-1px);
  }

  .path-box {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0;
    margin-top: 0.75rem;
  }

  .path-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .path-value {
    padding: 0.125rem 0.375rem;
    background: rgba(var(--theme-rgb-accent), 0.1);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.9rem;
    word-break: break-all;
  }

  .path-hint {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .instruction-list {
    margin: 0;
    padding-left: 1.25rem;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  .instruction-list li + li {
    margin-top: 0.5rem;
  }

  .instruction-list code {
    padding: 0.125rem 0.375rem;
    background: rgba(var(--theme-rgb-accent), 0.1);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.875rem;
  }

  @media (max-width: 768px) {
    .step-card {
      padding: 1.5rem;
    }

    .step-name-large {
      font-size: 1.125rem;
    }
  }

  @media (max-height: 700px) {
    .step-card {
      padding: 1rem;
    }
  }
</style>
