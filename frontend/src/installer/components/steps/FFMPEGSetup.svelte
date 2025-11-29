<script lang="ts">
  import { onMount } from "svelte";
  import {
    Download,
    ExternalLink,
    FolderOpen,
    Info,
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

  let currentSubStepIndex = 0;

  // 親コンポーネントに通知するためのフラグ
  export let canGoBack = false;
  export let isStepCompleted = false;

  $: isStepCompleted = setupCompleted.downloadAndExtract;

  $: canGoBack = currentSubStepIndex > 0;

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

  export async function next(
    options: { skip?: boolean } = {}
  ): Promise<boolean> {
    if (!ffmpegInstalled) {
      await handleSetup();
      if (!ffmpegInstalled) {
        alert(
          "FFMPEG が検出されませんでした。インストールしてから次へ進んでください。"
        );
        return true;
      }
    }

    if (!options.skip && !setupCompleted.downloadAndExtract) {
      await markSubstepCompleted(
        InstallationStep.FFMPEG_SETUP,
        "ffmpeg-download-extract",
        true
      );
    }

    // Only one step, so return false to proceed to next page
    return false;
  }

  export async function back(): Promise<boolean> {
    // No sub-steps to go back to
    return false;
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
          true
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
      if (ffmpegInstalled) return;

      await markSubstepCompleted(
        InstallationStep.FFMPEG_SETUP,
        "ffmpeg-download-extract",
        false
      );
      return;
    }

    isChecking = true;
    checkError = null;

    try {
      const result = await setupFFMPEG();

      if (result.is_installed) {
        ffmpegInstalled = true;
        ffmpegVersion = result.version || null;
        setupCompleted.downloadAndExtract = true;
        await markSubstepCompleted(
          InstallationStep.FFMPEG_SETUP,
          "ffmpeg-download-extract",
          true
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

  function handleCardClick(event: Event) {
    if (isChecking || (setupCompleted.downloadAndExtract && ffmpegInstalled)) {
      return;
    }

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
      (target.closest("button") ||
        target.closest("a") ||
        target.closest("input") ||
        target.closest(".path-value"))
    ) {
      return;
    }

    handleSetup();
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      handleCardClick(event);
    }
  }
</script>

<div class="ffmpeg-setup">
  <div class="step-header">
    <div class="title-container">
      <h2 class="step-title">FFMPEG セットアップ</h2>
      <div class="tooltip-container">
        <Info class="info-icon" size={20} />
        <div class="tooltip-content glass-card">
          <h3 class="tooltip-title">FFMPEG について</h3>
          <p class="tooltip-text">
            FFMPEG は動画・音声ファイルの変換、編集、ストリーミングを行うための
            オープンソースのマルチメディアフレームワークです。Splat Replay
            では、 録画した動画のトリミングや形式変換に使用します。
          </p>
        </div>
      </div>
    </div>
    <p class="step-description">
      動画編集に使用するため、 FFMPEG をインストールします
    </p>
  </div>

  <div class="setup-steps-section">
    <div
      class="step-card glass-card"
      class:completed={setupCompleted.downloadAndExtract}
      class:disabled={isChecking ||
        (setupCompleted.downloadAndExtract && ffmpegInstalled)}
      on:click={handleCardClick}
      on:keydown={handleKeyDown}
      role="button"
      tabindex="0"
    >
      <div class="step-content-wrapper">
        <div class="card-header">
          <div class="header-left">
            <div class="step-number-large">1</div>
            <div class="title-wrapper">
              <h3 class="step-name-large">FFMPEGのインストール</h3>
              {#if ffmpegInstalled}
                <span class="installed-badge">インストール済</span>
              {/if}
            </div>
          </div>
          <div
            class="checkbox-indicator"
            class:checked={setupCompleted.downloadAndExtract}
          >
            {#if setupCompleted.downloadAndExtract}
              <Check size={20} />
            {/if}
          </div>
        </div>

        <div class="card-body">
          <ol class="instruction-list">
            <li>
              FFMPEG 配布先から最新版(Latest)を探す
              <div style="margin-top: 1rem;">
                <button
                  class="link-button"
                  type="button"
                  on:click={() =>
                    openUrl(
                      "https://github.com/BtbN/FFmpeg-Builds/releases/tag/latest"
                    )}
                >
                  <Download class="icon" size={16} />
                  FFMPEG をダウンロード
                  <ExternalLink class="icon" size={14} />
                </button>
              </div>
            </li>
            <li>
              「Assets」エリアから「ffmpeg-*-win64-gpl-shared.zip」をダウンロードします
            </li>
            <li>
              ダウンロードした ZIP ファイルを展開し、フォルダ名を <code
                >ffmpeg</code
              >
              に変更して Cドライブ直下に配置します
            </li>
            <li>
              下記のフォルダに「ffmpeg.exe」があることを確認します
              <div class="path-box">
                <FolderOpen class="icon" size={20} />
                <div class="path-content">
                  <code class="path-value">C:\ffmpeg\bin</code>
                </div>
              </div>
            </li>
          </ol>
          <p class="step-note">
            ※ 配置後、カードをクリックすると、自動的に環境変数 PATH
            の設定とインストール確認が行われます。
          </p>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .ffmpeg-setup {
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
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .title-container {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    justify-content: center;
  }

  .step-title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .tooltip-container {
    position: relative;
    display: flex;
    align-items: center;
    cursor: help;
  }

  :global(.info-icon) {
    color: var(--text-secondary);
    transition: color 0.2s;
  }

  .tooltip-container:hover :global(.info-icon) {
    color: var(--accent-color);
  }

  .tooltip-content {
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%) translateY(10px);
    width: 300px;
    padding: 1rem;
    background: rgba(20, 20, 30, 0.95);
    border: 1px solid rgba(25, 211, 199, 0.2);
    border-radius: 12px;
    opacity: 0;
    visibility: hidden;
    transition: all 0.2s ease;
    z-index: 100;
    pointer-events: none;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }

  .tooltip-container:hover .tooltip-content {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) translateY(5px);
  }

  .tooltip-title {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--accent-color);
  }

  .tooltip-text {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.5;
    color: var(--text-secondary);
    text-align: left;
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
    background: linear-gradient(
      135deg,
      rgba(25, 211, 199, 0.2) 0%,
      rgba(25, 211, 199, 0.05) 100%
    );
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
    background: linear-gradient(
      135deg,
      var(--accent-color) 0%,
      var(--accent-color-strong) 100%
    );
    color: white;
    box-shadow: 0 0 8px var(--accent-glow);
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
    margin-top: 0.75rem;
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
    gap: 0.4rem;
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
    font-size: 0.9rem;
    word-break: break-all;
  }

  .path-hint {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .step-note {
    margin: 1rem 0 0 0;
    font-size: 0.85rem;
    font-style: italic;
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
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.875rem;
  }

  .icon {
    display: block;
    flex-shrink: 0;
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
