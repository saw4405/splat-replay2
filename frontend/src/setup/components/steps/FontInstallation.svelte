<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { Check, FolderOpen, RefreshCw } from 'lucide-svelte';
  import { checkSystem } from '../../stores/system';
  import { markSubstepCompleted } from '../../stores/navigation';
  import { setupState } from '../../stores/state';
  import { type SystemCheckResult, SetupStep } from '../../types';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';
  import { getSetupPlatform, MACOS_APPLICATION_SUPPORT_DIR } from '../../platform';

  const setupPlatform = getSetupPlatform();

  const SUBSTEP_STORAGE_KEY = 'font_substep_index';

  interface SetupStepItem {
    id: string;
    title: string;
    description: string;
    completed: boolean;
  }

  let fontAvailable = $state(false);
  let customFontInstalled = $state(false);
  let _fontPath = $state<string | null>(null);
  let isChecking = $state(false);
  let hasInitializedSubstep = $state(false);
  let dialogOpen = $state(false);
  let dialogMessage = $state('');
  let dialogVariant = $state<'info' | 'success' | 'warning' | 'error'>('info');

  let setupSteps: SetupStepItem[] = $state([
    {
      id: 'font-download',
      title: 'イカモドキフォント（任意）',
      description: 'お持ちの場合は配置すると、従来のサムネイルの見た目を維持できます。',
      completed: false,
    },
    {
      id: 'font-place',
      title: '日本語フォントを確認',
      description: '未配置の場合は OS 標準の日本語フォントを使います。',
      completed: false,
    },
  ]);

  let currentSubStepIndex = $state(0);

  // 親コンポーネントに通知するためのフラグ
  interface Props {
    canGoBack?: boolean;
    isStepCompleted?: boolean;
  }

  let { canGoBack = $bindable(false), isStepCompleted = $bindable(false) }: Props = $props();

  $effect(() => {
    isStepCompleted = setupSteps[currentSubStepIndex].completed;
  });

  $effect(() => {
    canGoBack = currentSubStepIndex > 0;
  });

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

  function computeInitialSubstepIndex(_steps: SetupStepItem[]): number {
    // 常に最初の手順から開始する
    return 0;
  }

  // 現在のステップが変更されたときにhasInitializedSubstepをリセット
  $effect(() => {
    if ($setupState?.current_step !== SetupStep.FONT_INSTALLATION) {
      hasInitializedSubstep = false;
    }
  });

  // Sync with installation state
  $effect(() => {
    if ($setupState && $setupState.step_details) {
      const details = $setupState.step_details[SetupStep.FONT_INSTALLATION] || {};
      // untrack で setupSteps を依存関係から外す（楽観的更新が $effect で上書きされるのを防ぐ）
      const updatedSteps = untrack(() => setupSteps).map((step) => ({
        ...step,
        completed: details[step.id] || false,
      }));
      setupSteps = updatedSteps;

      if (!hasInitializedSubstep && $setupState.current_step === SetupStep.FONT_INSTALLATION) {
        const savedIndex = loadSavedSubstepIndex(updatedSteps.length - 1);
        if (savedIndex !== null) {
          currentSubStepIndex = savedIndex;
        } else {
          currentSubStepIndex = computeInitialSubstepIndex(updatedSteps);
        }
        hasInitializedSubstep = true;
      }
    }
  });

  $effect(() => {
    if (hasInitializedSubstep) {
      saveSubstepIndex(currentSubStepIndex);
    }
  });

  export async function next(options: { skip?: boolean } = {}): Promise<boolean> {
    const currentStep = setupSteps[currentSubStepIndex];

    if (!fontAvailable) {
      await checkFontInstallation();
      if (!fontAvailable && !options.skip) {
        showDialog(
          '日本語フォントを利用できないため、サムネイル生成に失敗します。フォントを導入後に再確認するか、このセットアップ手順をスキップしてください。',
          'error'
        );
        return true;
      }
      if (!fontAvailable) return false;
    }

    if (!options.skip && !currentStep.completed) {
      await markSubstepCompleted(SetupStep.FONT_INSTALLATION, currentStep.id, true);
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
      fontAvailable = result.is_installed;
      _fontPath = result.installation_path || null;
      customFontInstalled = _fontPath?.split(/[\\/]/).pop()?.toLowerCase() === 'ikamodoki1.ttf';

      await markSubstepCompleted(SetupStep.FONT_INSTALLATION, setupSteps[0].id, fontAvailable);
      await markSubstepCompleted(SetupStep.FONT_INSTALLATION, setupSteps[1].id, fontAvailable);
    } catch (error) {
      fontAvailable = false;
      customFontInstalled = false;
      await markSubstepCompleted(SetupStep.FONT_INSTALLATION, setupSteps[0].id, false);
      await markSubstepCompleted(SetupStep.FONT_INSTALLATION, setupSteps[1].id, false);
      console.error('Font check failed', error);
    } finally {
      isChecking = false;
    }
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

<div class="font-installation">
  <div class="step-header">
    <h2 class="step-title">サムネイル用フォント</h2>
    <p class="step-description">
      イカモドキフォントがあれば従来の見た目を保ち、無ければ OS 標準の日本語フォントを使います。
    </p>
  </div>

  <div class="setup-steps-section">
    <div class="step-card glass-card" class:completed={setupSteps[currentSubStepIndex].completed}>
      {#key currentSubStepIndex}
        <div class="step-content-wrapper">
          <div class="card-header">
            <div class="header-left">
              <div class="step-number-large">{currentSubStepIndex + 1}</div>
              <div class="title-wrapper">
                <h3 class="step-name-large">
                  {setupSteps[currentSubStepIndex].title}
                </h3>
                {#if fontAvailable}
                  <span class="installed-badge">
                    {customFontInstalled ? 'イカモドキを使用' : 'OS 標準を使用'}
                  </span>
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
              <p>{setupSteps[currentSubStepIndex].description}</p>
              <p class="step-note">
                作者による配布は終了しています。お持ちのファイルを使う場合は、下記へ
                <code>ikamodoki1.ttf</code> を配置してください。
              </p>
              <div class="path-box">
                <FolderOpen class="icon" size={20} />
                <div class="path-content">
                  <code class="path-value">
                    {setupPlatform === 'macos'
                      ? `${MACOS_APPLICATION_SUPPORT_DIR}/assets/thumbnail`
                      : setupPlatform === 'windows'
                        ? 'SplatReplay\\assets\\thumbnail'
                        : 'アプリの assets/thumbnail フォルダ'}
                  </code>
                </div>
              </div>
            {:else if currentSubStepIndex === 1}
              <p>{setupSteps[currentSubStepIndex].description}</p>
              {#if isChecking}
                <p role="status">日本語フォントを確認しています…</p>
              {:else if fontAvailable && !customFontInstalled}
                <p role="status">
                  ikamodoki1.ttf がないため、OS 標準の日本語フォントを使用します。
                </p>
              {:else if fontAvailable}
                <p role="status">ikamodoki1.ttf を使用できます。</p>
              {:else}
                <p role="alert">
                  利用可能な日本語フォントがありません。フォントを導入して再確認するか、このセットアップ手順をスキップしてください。
                </p>
                <button class="link-button" type="button" onclick={checkFontInstallation}>
                  <RefreshCw class="icon" size={16} />
                  インストール状態を再確認
                </button>
              {/if}
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
    onClose={() => (dialogOpen = false)}
  />
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
    transition: all 0.2s ease;
    outline: none;
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

  .checkbox-indicator.checked {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: var(--theme-color-charcoal);
    box-shadow: 0 0 4px var(--accent-glow);
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

  .step-name-large {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-primary);
    text-align: left;
  }

  .card-body::-webkit-scrollbar {
    width: 8px;
  }

  .card-body::-webkit-scrollbar-thumb {
    background: rgba(var(--theme-rgb-white), 0.2);
    border-radius: 4px;
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
    box-shadow: 0 0 4px var(--accent-glow);
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
    background: rgba(var(--theme-rgb-accent), 0.1);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.875rem;
    word-break: break-all;
  }
</style>
