<script lang="ts">
  import { onMount } from "svelte";
  import {
    Download,
    ExternalLink,
    Settings,
    RefreshCw,
    Check,
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
    description: string;
    completed: boolean;
    url?: string;
  }

  let obsInstalled = false;
  let obsVersion: string | null = null;
  let obsPath: string | null = null;
  let isChecking = false;
  let checkingIndex: number | null = null;

  let ndiInstalled = false;
  let ndiVersion: string | null = null;
  let ndiPath: string | null = null;

  let setupSteps: SetupStep[] = [
    {
      id: "obs-install",
      title: "OBS Studio のインストール",
      description:
        "OBS Studio 公式サイトから最新版をダウンロードしてインストールしてください。",
      completed: false,
      url: "https://obsproject.com/ja/download",
    },
    {
      id: "obs-ndi",
      title: "obs-ndi プラグインのインストール",
      description: "",
      completed: false,
      url: "https://github.com/obs-ndi/obs-ndi/releases",
    },
    {
      id: "ndi-runtime",
      title: "NDI 6 Runtime のインストール",
      description: "",
      completed: false,
      url: "https://obsproject.com/",
    },
    {
      id: "video-capture-device",
      title: "映像キャプチャデバイスの追加",
      description: "",
      completed: false,
    },
    {
      id: "ndi-settings",
      title: "OBS NDI 設定",
      description: "",
      completed: false,
    },
    {
      id: "recording-settings",
      title: "OBS 録画設定",
      description: "",
      completed: false,
    },
  ];

  onMount(async () => {
    await checkOBSInstallation();
    await checkNDIInstallation();
  });

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.OBS_SETUP] || {};
    setupSteps = setupSteps.map((step) => ({
      ...step,
      completed: details[step.id] || false,
    }));
  }

  async function checkOBSInstallation(): Promise<void> {
    isChecking = true;
    checkingIndex = 0;

    try {
      const result: SystemCheckResult = await checkSystem("obs");
      obsInstalled = result.is_installed;
      obsVersion = result.version || null;
      obsPath = result.installation_path || null;

      if (obsInstalled) {
        await markSubstepCompleted(
          InstallationStep.OBS_SETUP,
          setupSteps[0].id,
          true,
        );
      }
    } catch (error) {
      console.error("OBS check failed", error);
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function checkNDIInstallation(): Promise<void> {
    isChecking = true;
    checkingIndex = 2;
    try {
      const result: SystemCheckResult = await checkSystem("ndi");
      ndiInstalled = result.is_installed;
      ndiVersion = result.version || null;
      ndiPath = result.installation_path || null;

      if (ndiInstalled) {
        await markSubstepCompleted(
          InstallationStep.OBS_SETUP,
          setupSteps[2].id,
          true,
        );
      }
    } catch (error) {
      console.warn("NDI Runtime check failed:", error);
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    if (step.completed) {
      // Prevent unchecking if installed
      if (index === 0 && obsInstalled) return;
      if (index === 2 && ndiInstalled) return;

      await markSubstepCompleted(InstallationStep.OBS_SETUP, step.id, false);
      return;
    }

    if (index === 0) {
      await checkOBSInstallation();
      if (!obsInstalled) {
        alert("OBS Studio が検出されませんでした。");
      }
    } else if (index === 2) {
      await checkNDIInstallation();
      if (!ndiInstalled) {
        alert("NDI Runtime が検出されませんでした。");
      }
    } else {
      await markSubstepCompleted(InstallationStep.OBS_SETUP, step.id, true);
    }
  }

  function openUrl(url: string): void {
    window.open(url, "_blank");
  }
</script>

<div class="obs-setup">
  <div class="step-header">
    <h2 class="step-title">OBS Studio セットアップ</h2>
    <p class="step-description">
      OBS Studio と必要なプラグインをインストールし、録画設定を行います。
    </p>
  </div>

  <div class="setup-steps-section">
    <!-- Step 1: OBS Studio Installation -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">1</div>
        <div class="step-info">
          <h4 class="step-name">
            OBS Studio のインストール
            {#if obsInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupSteps[0].completed}
            <div class="instructions">
              <ol>
                <li>
                  OBS Studio
                  公式サイトから最新版をダウンロードしてインストールしてください
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl("https://obsproject.com/ja/download")}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[0].completed}
          on:click={() => toggleStep(0)}
          aria-label={setupSteps[0].completed ? "完了を解除" : "完了にする"}
          disabled={isChecking || obsInstalled}
        >
          <div class="checkbox-box" class:checked={setupSteps[0].completed}>
            {#if isChecking && checkingIndex === 0}
              <RefreshCw class="icon spinning" size={20} />
            {:else if setupSteps[0].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <!-- Step 2: obs-ndi Plugin Installation -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">2</div>
        <div class="step-info">
          <h4 class="step-name">obs-ndi プラグインのインストール</h4>
          {#if !setupSteps[1].completed}
            <div class="instructions">
              <ol>
                <li>
                  GitHubの「Releases」ページから最新版(Latest)を探す
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl("https://github.com/obs-ndi/obs-ndi/releases")}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>
                  「Assets」エリアから「Windows-x64-installer.exe」をダウンロード
                </li>
                <li>インストーラーを実行してインストールを完了</li>
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
        >
          <div class="checkbox-box" class:checked={setupSteps[1].completed}>
            {#if setupSteps[1].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <!-- Step 3: NDI Runtime Installation -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">3</div>
        <div class="step-info">
          <h4 class="step-name">
            NDI 6 Runtime のインストール
            {#if ndiInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupSteps[2].completed}
            <div class="instructions">
              <ol>
                <li>
                  NDI 公式サイトにアクセス
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() => openUrl("https://obsproject.com/")}
                    >
                      <Download class="icon" size={16} />
                      ダウンロードページを開く
                      <ExternalLink class="icon" size={14} />
                    </button>
                  </div>
                </li>
                <li>「Download (.msi)」のリンクをクリック</li>
                <li>NDI Runtimeをダウンロードしてインストールを完了</li>
              </ol>
            </div>
            <p class="step-note">
              ※ NDI
              Runtimeをインストールする前にOBSを起動するとエラーが表示されます
            </p>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[2].completed}
          on:click={() => toggleStep(2)}
          aria-label={setupSteps[2].completed ? "完了を解除" : "完了にする"}
          disabled={isChecking || ndiInstalled}
        >
          <div class="checkbox-box" class:checked={setupSteps[2].completed}>
            {#if isChecking && checkingIndex === 2}
              <RefreshCw class="icon spinning" size={20} />
            {:else if setupSteps[2].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <!-- Step 4: Video Capture Device -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">4</div>
        <div class="step-info">
          <h4 class="step-name">OBS キャプチャ設定</h4>
          {#if !setupSteps[3].completed}
            <div class="instructions">
              <ol>
                <li>OBSの「ソース」パネルの「+」ボタンをクリック</li>
                <li>「映像キャプチャデバイス」を選択</li>
                <li>キャプチャーデバイスを選択</li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[3].completed}
          on:click={() => toggleStep(3)}
          aria-label={setupSteps[3].completed ? "完了を解除" : "完了にする"}
        >
          <div class="checkbox-box" class:checked={setupSteps[3].completed}>
            {#if setupSteps[3].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <!-- Step 5: NDI Settings -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">5</div>
        <div class="step-info">
          <h4 class="step-name">OBS NDI 設定</h4>
          {#if !setupSteps[4].completed}
            <div class="instructions">
              <ol>
                <li>
                  OBS の「ツール」メニューから「DistroAV NDI
                  Settings」をクリック
                </li>
                <li>「Main Output」にチェックを入れる</li>
                <li>OKボタンをクリックして設定画面を閉じる</li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[4].completed}
          on:click={() => toggleStep(4)}
          aria-label={setupSteps[4].completed ? "完了を解除" : "完了にする"}
        >
          <div class="checkbox-box" class:checked={setupSteps[4].completed}>
            {#if setupSteps[4].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <!-- Step 6: Recording Settings -->
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">6</div>
        <div class="step-info">
          <h4 class="step-name">OBS 録画設定</h4>
          {#if !setupSteps[5].completed}
            <p class="step-desc">
              OBS の設定で録画フォーマット・品質を設定してください。
            </p>
            <div class="instructions">
              <p style="margin: 0.5rem 0 0 0; font-weight: 600;">推奨設定:</p>
              <ul style="margin: 0.5rem 0; padding-left: 1.5rem;">
                <li>フォーマット: MKV</li>
                <li>解像度: 1920x1080 (1080p)</li>
                <li>フレームレート: 30 FPS 以上</li>
                <li>エンコーダ: ハードウェアエンコーダ(H.264やHEVC等)推奨</li>
              </ul>
            </div>
            <p class="step-note">
              ※
              一度録画をしてみて、映像のカクツキや音声の乱れがないか確認することを推奨します。
            </p>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupSteps[5].completed}
          on:click={() => toggleStep(5)}
          aria-label={setupSteps[5].completed ? "完了を解除" : "完了にする"}
        >
          <div class="checkbox-box" class:checked={setupSteps[5].completed}>
            {#if setupSteps[5].completed}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .obs-setup {
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

  .steps-list {
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

  .step-desc {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: var(--text-secondary);
    white-space: pre-line;
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

  .instructions {
    margin: 0;
  }

  .instructions ol,
  .instructions ul {
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

  .step-note {
    margin: 0.5rem 0 0 0;
    font-size: 0.875rem;
    font-style: italic;
    color: var(--text-secondary);
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
    .obs-setup {
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
