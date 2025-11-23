<script lang="ts">
  import { onMount } from "svelte";
  import {
    Download,
    ExternalLink,
    Check,
    RefreshCw,
    FolderOpen,
  } from "lucide-svelte";
  import {
    checkSystem,
    markSubstepCompleted,
    installationState,
  } from "../../store";
  import { type SystemCheckResult, InstallationStep } from "../../types";

  interface SetupStep {
    id: string;
    title: string;
    completed: boolean;
  }

  let fontInstalled = false;
  let fontPath: string | null = null;
  let isChecking = false;
  let checkingIndex: number | null = null;

  let setupSteps: SetupStep[] = [
    {
      id: "font-download",
      title: "イカモドキフォントをダウンロード",
      completed: false,
    },
    {
      id: "font-place",
      title: "イカモドキフォントを配置",
      completed: false,
    },
  ];

  onMount(async () => {
    await checkFontInstallation();
  });

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.FONT_INSTALLATION] || {};
    setupSteps = setupSteps.map((step) => ({
      ...step,
      completed: details[step.id] || false,
    }));
  }

  async function checkFontInstallation(): Promise<void> {
    isChecking = true;
    checkingIndex = 1;

    try {
      const result: SystemCheckResult = await checkSystem("font");
      fontInstalled = result.is_installed;
      fontPath = result.installation_path || null;

      if (fontInstalled) {
        await markSubstepCompleted(
          InstallationStep.FONT_INSTALLATION,
          setupSteps[0].id,
          true,
        );
        await markSubstepCompleted(
          InstallationStep.FONT_INSTALLATION,
          setupSteps[1].id,
          true,
        );
      }
    } catch (error) {
      console.error("Font check failed", error);
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    if (step.completed) {
      // Prevent unchecking if installed (both steps)
      if (fontInstalled) return;

      await markSubstepCompleted(
        InstallationStep.FONT_INSTALLATION,
        step.id,
        false,
      );
      return;
    }

    // For step 2 (font placement), check installation
    if (index === 1) {
      await checkFontInstallation();
      if (!fontInstalled) {
        alert("フォントファイルが見つかりませんでした。");
      }
    } else {
      await markSubstepCompleted(
        InstallationStep.FONT_INSTALLATION,
        step.id,
        true,
      );
    }
  }

  function openUrl(url: string): void {
    window.open(url, "_blank");
  }
</script>

<div class="font-installation">
  <div class="step-header">
    <h2 class="step-title">イカモドキフォントのインストール</h2>
    <p class="step-description">
      サムネイル生成に使用するイカモドキフォントをダウンロードし、アプリケーションフォルダに配置します。
      スプラトゥーンの雰囲気を再現するために推奨されます。
    </p>
  </div>

  <div class="setup-steps-section">
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">1</div>
        <div class="step-info">
          <h4 class="step-name">
            イカモドキフォントをダウンロード
            {#if fontInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupSteps[0].completed}
            <div class="instructions">
              <ol>
                <li>
                  イカモドキフォント配布ページからフォントファイルをダウンロードする
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://web.archive.org/web/20150906013956/http://aramugi.com/?page_id=807",
                        )}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
              </ol>
              <div class="info-box">
                <p>※ イカモドキフォントはシステムにインストールしません</p>
              </div>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[0].completed}
          on:click={() => toggleStep(0)}
          aria-label={setupSteps[0].completed ? "完了を解除" : "完了にする"}
          disabled={fontInstalled}
        >
          <div class="checkbox-box" class:checked={setupSteps[0].completed}>
            {#if setupSteps[0].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">2</div>
        <div class="step-info">
          <h4 class="step-name">
            イカモドキフォントを配置
            {#if fontInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupSteps[1].completed}
            <div class="instructions">
              <ol>
                <li>
                  ダウンロードしたイカモドキフォント（<code>ikamodoki1.ttf</code
                  >）をアプリケーションフォルダに配置
                  <div class="path-box">
                    <FolderOpen class="icon" size={20} />
                    <div class="path-content">
                      <p class="path-label">配置先フォルダ:</p>
                      <code class="path-value"
                        >_internal\assets\thumbnail\ikamodoki1.ttf</code
                      >
                    </div>
                  </div>
                </li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[1].completed}
          on:click={() => toggleStep(1)}
          aria-label={setupSteps[1].completed ? "完了を解除" : "完了にする"}
          disabled={isChecking || fontInstalled}
        >
          <div class="checkbox-box" class:checked={setupSteps[1].completed}>
            {#if isChecking && checkingIndex === 1}
              <RefreshCw class="icon spinning" size={20} />
            {:else if setupSteps[1].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .font-installation {
    display: flex;
    flex-direction: column;
    gap: 2rem;
    padding: 1rem;
  }

  .step-header {
    text-align: left;
  }

  .step-title {
    margin: 0 0 1rem 0;
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .step-description {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  .icon.spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .setup-steps-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .step-card {
    padding: 1.5rem;
    transition: all 0.3s ease;
  }

  .step-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  }

  .step-content {
    display: flex;
    align-items: flex-start;
    gap: 1.5rem;
  }

  .step-number {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(
      135deg,
      rgba(25, 211, 199, 0.2) 0%,
      rgba(25, 211, 199, 0.05) 100%
    );
    border: 2px solid rgba(25, 211, 199, 0.3);
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--accent-color);
  }

  .step-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .step-name {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    text-align: left;
  }

  .installed-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 999px;
    background: linear-gradient(
      135deg,
      var(--accent-color) 0%,
      var(--accent-color-strong) 100%
    );
    color: white;
    box-shadow: 0 0 8px var(--accent-glow);
  }

  .instructions {
    padding: 0;
    margin-top: 0.5rem;
  }

  .instructions ol {
    margin: 0;
    padding-left: 1.5rem;
  }

  .instructions li {
    margin-bottom: 0.5rem;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: var(--text-secondary);
    text-align: left;
  }

  .instructions li:last-child {
    margin-bottom: 0;
  }

  .instructions code {
    padding: 0.125rem 0.375rem;
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.875rem;
  }

  .info-box {
    padding: 0;
    margin-top: 0.5rem;
  }

  .info-box p {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: var(--text-secondary);
    text-align: left;
  }

  .link-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 6px;
    border: 1px solid rgba(25, 211, 199, 0.3);
    background: rgba(25, 211, 199, 0.1);
    color: var(--accent-color);
    cursor: pointer;
    transition: all 0.2s ease;
    align-self: flex-start;
  }

  .link-button:hover {
    background: rgba(25, 211, 199, 0.2);
    border-color: rgba(25, 211, 199, 0.5);
    transform: translateY(-1px);
  }

  .path-box {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0;
    margin-top: 0.5rem;
  }

  .path-box .icon {
    color: var(--accent-color);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .path-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .path-label {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-align: left;
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

  .step-checkbox {
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: transparent;
    cursor: pointer;
    transition: all 0.2s ease;
    padding: 0;
  }

  .step-checkbox:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .step-checkbox:hover:not(:disabled) {
    transform: scale(1.1);
  }

  .checkbox-box {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    background: rgba(0, 0, 0, 0.2);
    transition: all 0.3s ease;
  }

  .checkbox-box.checked {
    background: linear-gradient(
      135deg,
      var(--accent-color) 0%,
      var(--accent-color-strong) 100%
    );
    border-color: var(--accent-color);
    box-shadow: 0 0 12px var(--accent-glow);
  }

  .check-icon {
    color: white;
  }

  .icon {
    display: block;
    flex-shrink: 0;
  }

  @media (max-width: 768px) {
    .font-installation {
      padding: 0.5rem;
      gap: 1.5rem;
    }

    .step-title {
      font-size: 1.5rem;
    }

    .step-content {
      flex-direction: column;
      gap: 1rem;
    }
  }
</style>
