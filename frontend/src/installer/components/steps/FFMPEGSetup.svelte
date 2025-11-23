<script lang="ts">
  import { onMount } from "svelte";
  import {
    Download,
    ExternalLink,
    Terminal,
    RefreshCw,
    Check,
  } from "lucide-svelte";
  import {
    checkSystem,
    setupFFMPEG,
    markSubstepCompleted,
    installationState,
  } from "../../store";
  import { type SystemCheckResult, InstallationStep } from "../../types";

  let ffmpegInstalled = false;
  let ffmpegVersion: string | null = null;
  let isChecking = false;
  let checkError: string | null = null;

  let setupCompleted = {
    downloadAndExtract: false,
  };

  onMount(async () => {
    await checkFFMPEGInstallation();
  });

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.FFMPEG_SETUP] || {};
    setupCompleted = {
      downloadAndExtract: details["ffmpeg-download-extract"] || false,
    };
  }

  async function checkFFMPEGInstallation(): Promise<void> {
    isChecking = true;
    checkError = null;

    try {
      const result: SystemCheckResult = await checkSystem("ffmpeg");
      ffmpegInstalled = result.is_installed;
      ffmpegVersion = result.version || null;

      if (ffmpegInstalled) {
        await markSubstepCompleted(
          InstallationStep.FFMPEG_SETUP,
          "ffmpeg-download-extract",
          true,
        );
      }
    } catch (error) {
      checkError =
        error instanceof Error
          ? error.message
          : "FFMPEG のインストール確認に失敗しました";
    } finally {
      isChecking = false;
    }
  }

  async function handleSetup(): Promise<void> {
    if (setupCompleted.downloadAndExtract) {
      // 既に完了している場合は解除不可（インストール済の場合）
      if (ffmpegInstalled) return;

      await markSubstepCompleted(
        InstallationStep.FFMPEG_SETUP,
        "ffmpeg-download-extract",
        false,
      );
      return;
    }

    // セットアップ実行（PATH追加と確認）
    isChecking = true;
    checkError = null;

    try {
      const result = await setupFFMPEG();

      if (result.is_installed) {
        ffmpegInstalled = true;
        ffmpegVersion = result.version || null;
        setupCompleted.downloadAndExtract = true; // UIを即座に更新
        await markSubstepCompleted(
          InstallationStep.FFMPEG_SETUP,
          "ffmpeg-download-extract",
          true,
        );
      } else {
        checkError = result.error_message || "セットアップに失敗しました";
        setupCompleted.downloadAndExtract = false;
        alert(checkError);
      }
    } catch (error) {
      checkError =
        error instanceof Error
          ? error.message
          : "セットアップ中にエラーが発生しました";
      setupCompleted.downloadAndExtract = false;
      alert(checkError);
    } finally {
      isChecking = false;
    }
  }

  function openUrl(url: string): void {
    window.open(url, "_blank");
  }
</script>

<div class="ffmpeg-setup">
  <div class="step-header">
    <h2 class="step-title">FFMPEG セットアップ</h2>
    <p class="step-description">
      動画編集機能に必要な FFMPEG をインストールします。
    </p>
  </div>

  <div class="setup-steps-section">
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">1</div>
        <div class="step-info">
          <h4 class="step-name">
            FFMPEGのインストール
            {#if ffmpegInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupCompleted.downloadAndExtract}
            <div class="instructions">
              <ol>
                <li>
                  FFMPEG 配布先から最新版(Latest)を探す
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://github.com/BtbN/FFmpeg-Builds/releases",
                        )}
                    >
                      <Download class="icon" size={16} />
                      FFMPEG をダウンロード
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>
                  「Assets」エリアから「ffmpeg-*-win64-gpl-shared.zip」をダウンロード
                </li>
                <li>
                  ダウンロードした ZIP ファイルを展開し、フォルダ名を <code
                    >ffmpeg</code
                  >
                  に変更して Cドライブ直下に配置します
                  <div class="code-block" style="margin-top: 0.5rem;">
                    <Terminal class="icon" size={16} />
                    <code>C:\ffmpeg\bin\ffmpeg.exe</code>
                  </div>
                </li>
              </ol>
            </div>
            <p class="step-note">
              ※ 配置後、右のチェックボックスをオンにすると、自動的に環境変数
              PATH の設定とインストール確認が行われます。
            </p>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupCompleted.downloadAndExtract}
          on:click={handleSetup}
          disabled={isChecking ||
            (setupCompleted.downloadAndExtract && ffmpegInstalled)}
          aria-label={setupCompleted.downloadAndExtract
            ? "完了を解除"
            : "完了にする"}
        >
          <div
            class="checkbox-box"
            class:checked={setupCompleted.downloadAndExtract}
          >
            {#if isChecking}
              <RefreshCw class="check-icon spinning" size={20} />
            {:else if setupCompleted.downloadAndExtract}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>
  </div>

  <div class="info-card glass-card">
    <h3 class="info-title">FFMPEG について</h3>
    <p class="info-text">
      FFMPEG は動画・音声ファイルの変換、編集、ストリーミングを行うための
      オープンソースのマルチメディアフレームワークです。Splat Replay では、
      録画した動画のトリミングや形式変換に使用します。
    </p>
  </div>
</div>

<style>
  .ffmpeg-setup {
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

  .code-block {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    font-family: monospace;
  }

  .code-block .icon {
    color: var(--accent-color);
  }

  .code-block code {
    color: var(--text-primary);
    font-size: 0.9375rem;
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

  .info-card {
    padding: 1.5rem;
    background: rgba(25, 211, 199, 0.05);
    border-color: rgba(25, 211, 199, 0.2);
  }

  .info-title {
    margin: 0 0 1rem 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--accent-color);
  }

  .info-text {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  .icon {
    display: block;
    flex-shrink: 0;
  }

  .check-icon.spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 768px) {
    .ffmpeg-setup {
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
