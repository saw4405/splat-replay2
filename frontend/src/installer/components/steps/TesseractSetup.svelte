<script lang="ts">
  import { onMount } from "svelte";
  import { Download, ExternalLink, RefreshCw, Check } from "lucide-svelte";
  import {
    checkSystem,
    setupTesseract,
    markSubstepCompleted,
    installationState,
  } from "../../store";
  import { type SystemCheckResult, InstallationStep } from "../../types";

  let tesseractInstalled = false;
  let tesseractVersion: string | null = null;
  let isChecking = false;
  let checkingIndex: number | null = null;

  let setupCompleted = {
    install: false,
    langData: false,
  };

  onMount(async () => {
    await checkTesseractInstallation();
  });

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.TESSERACT_SETUP] || {};
    setupCompleted = {
      install: details["tesseract-install"] || false,
      langData: details["tesseract-lang-data"] || false,
    };
  }

  async function checkTesseractInstallation(): Promise<void> {
    isChecking = true;
    checkingIndex = 0;

    try {
      const result: SystemCheckResult = await checkSystem("tesseract");
      tesseractInstalled = result.is_installed;
      tesseractVersion = result.version || null;

      if (tesseractInstalled) {
        await markSubstepCompleted(
          InstallationStep.TESSERACT_SETUP,
          "tesseract-install",
          true,
        );
      }
    } catch (error) {
      console.error("Tesseract check failed", error);
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function toggleInstallStep(): Promise<void> {
    if (setupCompleted.install) {
      // Prevent unchecking if installed
      if (tesseractInstalled) return;

      await markSubstepCompleted(
        InstallationStep.TESSERACT_SETUP,
        "tesseract-install",
        false,
      );
      return;
    }

    // Check installation when user clicks checkbox
    isChecking = true;
    checkingIndex = 0;

    try {
      const result = await setupTesseract();

      if (result.is_installed) {
        tesseractInstalled = true;
        tesseractVersion = result.version || null;
        await markSubstepCompleted(
          InstallationStep.TESSERACT_SETUP,
          "tesseract-install",
          true,
        );
      } else {
        alert("Tesseract が検出されませんでした。");
      }
    } catch (error) {
      console.error("Tesseract setup failed", error);
      alert("Tesseract のセットアップに失敗しました。");
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function toggleLangDataStep(): Promise<void> {
    await markSubstepCompleted(
      InstallationStep.TESSERACT_SETUP,
      "tesseract-lang-data",
      !setupCompleted.langData,
    );
  }

  function openUrl(url: string): void {
    window.open(url, "_blank");
  }
</script>

<div class="tesseract-setup">
  <div class="step-header">
    <h2 class="step-title">Tesseract OCR セットアップ</h2>
    <p class="step-description">
      文字認識機能を使用するため、Tesseract OCR をインストールします。
    </p>
  </div>

  <div class="setup-steps-section">
    <!-- Step 1: Install -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">1</div>
        <div class="step-info">
          <h4 class="step-name">
            Tesseractのインストール
            {#if tesseractInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupCompleted.install}
            <div class="instructions">
              <ol>
                <li>
                  下のボタンからダウンロードページを開き、「tesseract-ocr-w64-setup-*.exe」をダウンロードします
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://github.com/UB-Mannheim/tesseract/wiki",
                        )}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>
                  インストーラーを実行してインストールします<br />
                </li>
              </ol>
            </div>
            <p class="step-note">
              ※
              インストール後、右のチェックボックスをオンにすると、自動的に環境変数
              PATH の設定とインストール確認が行われます。
            </p>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupCompleted.install}
          on:click={toggleInstallStep}
          disabled={(isChecking && checkingIndex === 0) ||
            (setupCompleted.install && tesseractInstalled)}
          aria-label={setupCompleted.install ? "完了を解除" : "完了にする"}
        >
          <div class="checkbox-box" class:checked={setupCompleted.install}>
            {#if isChecking && checkingIndex === 0}
              <RefreshCw class="icon spinning" size={20} />
            {:else if setupCompleted.install}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <!-- Step 2: Language Data -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">2</div>
        <div class="step-info">
          <h4 class="step-name">追加データの配置</h4>
          {#if !setupCompleted.langData}
            <div class="instructions">
              <ol>
                <li>
                  下のボタンからデータ配布ページを開き、「Download raw
                  file」ボタンをクリックしてダウンロードします
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://github.com/tesseract-ocr/tessdata_best/blob/main/eng.traineddata",
                        )}
                    >
                      <Download class="icon" size={16} />
                      eng.traineddata をダウンロード
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>
                  ダウンロードしたファイルを以下のフォルダに上書き保存します<br
                  />
                  <code>C:\Program Files\Tesseract-OCR\tessdata</code>
                </li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupCompleted.langData}
          on:click={toggleLangDataStep}
          aria-label={setupCompleted.langData ? "完了を解除" : "完了にする"}
        >
          <div class="checkbox-box" class:checked={setupCompleted.langData}>
            {#if setupCompleted.langData}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .tesseract-setup {
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
    gap: 0.75rem;
  }

  .step-name {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 0.75rem;
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

  .step-note {
    margin: 0;
    font-size: 0.875rem;
    font-style: italic;
    color: var(--text-secondary);
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

  .instructions {
    margin: 0;
  }

  .instructions ol {
    margin: 0;
    padding-left: 1.5rem;
    text-align: left;
  }

  .instructions li {
    margin-bottom: 0.5rem;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: var(--text-secondary);
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
    .tesseract-setup {
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
