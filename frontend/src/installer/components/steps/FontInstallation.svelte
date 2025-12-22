<script lang="ts">
  import { onMount } from 'svelte';
  import { Download, ExternalLink, Check, FolderOpen } from 'lucide-svelte';
  import { checkSystem, markSubstepCompleted, installationState } from '../../store';
  import { type SystemCheckResult, InstallationStep } from '../../types';

  const SUBSTEP_STORAGE_KEY = 'font_substep_index';

  interface SetupStep {
    id: string;
    title: string;
    description: string;
    completed: boolean;
  }

  let fontInstalled = false;
  let _fontPath: string | null = null;
  let isChecking = false;
  let hasInitializedSubstep = false;

  let setupSteps: SetupStep[] = [
    {
      id: 'font-download',
      title: 'イカモドキフォントをダウンロード',
      description: 'サムネイル生成に使用するイカモドキフォントをダウンロードします。',
      completed: false,
    },
    {
      id: 'font-place',
      title: 'イカモドキフォントを配置',
      description: 'ダウンロードしたフォントファイルをアプリケーションフォルダに配置します。',
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
    await checkFontInstallation();
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
  $: if ($installationState?.current_step !== InstallationStep.FONT_INSTALLATION) {
    hasInitializedSubstep = false;
  }

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details = $installationState.step_details[InstallationStep.FONT_INSTALLATION] || {};
    const updatedSteps = setupSteps.map((step) => ({
      ...step,
      completed: details[step.id] || false,
    }));
    setupSteps = updatedSteps;

    if (
      !hasInitializedSubstep &&
      $installationState.current_step === InstallationStep.FONT_INSTALLATION
    ) {
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

    // フォント配置ステップのバリデーション
    if (currentSubStepIndex === 1 && !fontInstalled) {
      await checkFontInstallation();
      if (!fontInstalled) {
        alert('フォントファイルが見つかりませんでした。配置してから次へ進んでください。');
        return true;
      }
    }

    if (!options.skip && !currentStep.completed) {
      await markSubstepCompleted(InstallationStep.FONT_INSTALLATION, currentStep.id, true);
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

  async function checkFontInstallation(): Promise<void> {
    isChecking = true;

    try {
      const result: SystemCheckResult = await checkSystem('font');
      fontInstalled = result.is_installed;
      _fontPath = result.installation_path || null;

      if (fontInstalled) {
        await markSubstepCompleted(InstallationStep.FONT_INSTALLATION, setupSteps[0].id, true);
        await markSubstepCompleted(InstallationStep.FONT_INSTALLATION, setupSteps[1].id, true);
      }
    } catch (error) {
      console.error('Font check failed', error);
    } finally {
      isChecking = false;
    }
  }

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    // Prevent unchecking if installed (both steps)
    if (fontInstalled) return;

    // For step 2 (font placement), check installation
    if (index === 1 && !step.completed) {
      await checkFontInstallation();
      if (!fontInstalled) {
        alert('フォントファイルが見つかりませんでした。');
      }
    } else {
      await markSubstepCompleted(InstallationStep.FONT_INSTALLATION, step.id, !step.completed);
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
</script>

<div class="font-installation">
  <div class="step-header">
    <h2 class="step-title">イカモドキフォントのダウンロード</h2>
    <p class="step-description">サムネイル生成に使用するイカモドキフォントをダウンロードします</p>
  </div>

  <div class="setup-steps-section">
    <div
      class="step-card glass-card"
      class:completed={setupSteps[currentSubStepIndex].completed}
      class:disabled={fontInstalled || (currentSubStepIndex === 1 && isChecking)}
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
                {#if fontInstalled}
                  <span class="installed-badge">配置済み</span>
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
              <!-- Font Download -->
              <ol class="instruction-list">
                <li>
                  イカモドキフォント配布ページからフォントファイルをダウンロードする
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          'https://web.archive.org/web/20150906013956/http://aramugi.com/?page_id=807'
                        )}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
              </ol>
              <p class="step-note">※ イカモドキフォントはシステムにインストールしません</p>
            {:else if currentSubStepIndex === 1}
              <!-- Font Placement -->
              <ol class="instruction-list">
                <li>
                  ダウンロードした ZIP ファイルを展開し、ファイル名を <code>ikamodoki1.ttf</code>
                  に変更して アプリケーションフォルダに配置します
                </li>
                <li>
                  ダウンロードしたイカモドキフォント（<code>ikamodoki1.ttf</code
                  >）を下記のフォルダに配置する
                  <div class="path-box">
                    <FolderOpen class="icon" size={20} />
                    <div class="path-content">
                      <code class="path-value">SplatReplay\assets\thumbnail</code>
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
</div>

<style>
  .font-installation {
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
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
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
    border-color: rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.05);
  }

  .step-card.completed {
    border-color: var(--accent-color);
    box-shadow: 0 0 15px rgba(25, 211, 199, 0.1);
    background: rgba(25, 211, 199, 0.05);
  }

  .step-card.disabled {
    cursor: default;
    opacity: 0.8;
  }

  .step-card.disabled:hover {
    border-color: rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.03);
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
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
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
    border: 2px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: transparent;
    transition: all 0.2s ease;
    background: rgba(255, 255, 255, 0.05);
  }

  .checkbox-indicator.checked {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #1a1a1a;
    box-shadow: 0 0 10px var(--accent-glow);
  }

  .step-card:hover .checkbox-indicator:not(.checked) {
    border-color: rgba(255, 255, 255, 0.4);
    background: rgba(255, 255, 255, 0.1);
  }

  .step-number-large {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.2) 0%, rgba(25, 211, 199, 0.05) 100%);
    border: 2px solid rgba(25, 211, 199, 0.3);
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
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
  }

  .card-body::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }

  .card-body::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  .installed-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    color: white;
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
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .link-button:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
  }

  .path-box {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0;
    margin-top: 0.5rem;
  }

  .path-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .path-value {
    padding: 0.125rem 0.375rem;
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.875rem;
    word-break: break-all;
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
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
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
