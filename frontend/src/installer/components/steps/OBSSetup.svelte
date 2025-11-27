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

  const SUBSTEP_STORAGE_KEY = "obs_substep_index";

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
        "OBS Studio 公式サイトから最新版をダウンロードしてインストールします",
      completed: false,
      url: "https://obsproject.com/ja/download",
    },
    {
      id: "obs-ndi",
      title: "obs-ndi プラグインのインストール",
      description:
        "GitHubからobs-ndiプラグインをダウンロードしてインストールします",
      completed: false,
      url: "https://github.com/obs-ndi/obs-ndi/releases",
    },
    {
      id: "ndi-runtime",
      title: "NDI 6 Runtime のインストール",
      description:
        "NDI公式サイトからRuntimeをダウンロードしてインストールします",
      completed: false,
      url: "https://obsproject.com/",
    },
    {
      id: "video-capture-device",
      title: "OBS キャプチャ設定",
      description: "OBSで映像キャプチャデバイスを追加します",
      completed: false,
    },
    {
      id: "ndi-settings",
      title: "OBS NDI 設定",
      description: "OBSのNDI設定を有効にします",
      completed: false,
    },
    {
      id: "recording-settings",
      title: "OBS 録画設定",
      description: "録画フォーマットや品質を設定します",
      completed: false,
    },
  ];

  let currentSubStepIndex = 0;
  let hasInitializedSubstep = false;

  // 親コンポーネントに通知するためのフラグ
  export let canGoBack = false;
  export let isStepCompleted = false;

  // obsInstalled, ndiInstalled の変更にも反応するように直接参照
  $: {
    const _obsInstalled = obsInstalled;
    const _ndiInstalled = ndiInstalled;
    const _currentIndex = currentSubStepIndex;
    const _steps = setupSteps;

    if (_currentIndex === 0) {
      isStepCompleted = _obsInstalled;
    } else if (_currentIndex === 2) {
      isStepCompleted = _ndiInstalled;
    } else {
      isStepCompleted = _steps[_currentIndex]?.completed || false;
    }
  }

  // UIで使用するためのreactive変数
  let currentStepChecked = false;
  $: {
    const _obsInstalled = obsInstalled;
    const _ndiInstalled = ndiInstalled;
    const _currentIndex = currentSubStepIndex;
    const _steps = setupSteps;

    if (_currentIndex === 0) {
      currentStepChecked = _obsInstalled;
    } else if (_currentIndex === 2) {
      currentStepChecked = _ndiInstalled;
    } else {
      currentStepChecked = _steps[_currentIndex]?.completed || false;
    }
  }

  $: canGoBack = currentSubStepIndex > 0;

  onMount(async () => {
    // Initial checks are handled by reactive statements below
  });

  function loadSavedSubstepIndex(maxIndex: number): number | null {
    if (typeof window === "undefined") return null;
    const stored = window.sessionStorage.getItem(SUBSTEP_STORAGE_KEY);
    if (stored === null) return null;
    const parsed = Number.parseInt(stored, 10);
    if (Number.isNaN(parsed)) return null;
    return Math.max(0, Math.min(parsed, maxIndex));
  }

  function saveSubstepIndex(index: number): void {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(SUBSTEP_STORAGE_KEY, index.toString());
  }

  function computeInitialSubstepIndex(steps: SetupStep[]): number {
    const firstIncomplete = steps.findIndex((step) => !step.completed);
    if (firstIncomplete !== -1) {
      return firstIncomplete;
    }
    return steps.length > 0 ? steps.length - 1 : 0;
  }

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.OBS_SETUP] || {};
    const updatedSteps = setupSteps.map((step) => ({
      ...step,
      completed: details[step.id] || false,
    }));
    setupSteps = updatedSteps;

    if (!hasInitializedSubstep) {
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

  // 手順1が表示されたときにOBSチェックを実行
  let lastCheckedOBSIndex = -1;
  $: if (
    hasInitializedSubstep &&
    currentSubStepIndex === 0 &&
    lastCheckedOBSIndex !== currentSubStepIndex
  ) {
    lastCheckedOBSIndex = currentSubStepIndex;
    checkOBSInstallation(false);
  }

  // 手順3が表示されたときにNDIチェックを実行
  let lastCheckedNDIIndex = -1;
  $: if (
    hasInitializedSubstep &&
    currentSubStepIndex === 2 &&
    lastCheckedNDIIndex !== currentSubStepIndex
  ) {
    lastCheckedNDIIndex = currentSubStepIndex;
    checkNDIInstallation(false);
  }

  export async function next(
    options: { skip?: boolean } = {},
  ): Promise<boolean> {
    const currentStep = setupSteps[currentSubStepIndex];

    // インストールチェックが必要なステップのバリデーション
    if (currentSubStepIndex === 0 && !obsInstalled) {
      await checkOBSInstallation(false);
      if (!obsInstalled) {
        alert(
          "OBS Studio が検出されませんでした。インストールしてから次へ進んでください。",
        );
        return true;
      }
    }

    if (currentSubStepIndex === 2 && !ndiInstalled) {
      await checkNDIInstallation(false);
      if (!ndiInstalled) {
        alert(
          "NDI Runtime が検出されませんでした。インストールしてから次へ進んでください。",
        );
        return true;
      }
    }

    if (!options.skip && !currentStep.completed) {
      await markSubstepCompleted(
        InstallationStep.OBS_SETUP,
        currentStep.id,
        true,
      );
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

  async function checkOBSInstallation(
    showError: boolean = false,
  ): Promise<void> {
    isChecking = true;
    checkingIndex = 0;

    try {
      const result: SystemCheckResult = await checkSystem("obs");
      obsInstalled = result.is_installed;
      obsVersion = result.version || null;
      obsPath = result.installation_path || null;

      console.log("[OBSSetup] OBS check result:", {
        obsInstalled,
        obsVersion,
        obsPath,
        currentCompleted: setupSteps[0]?.completed,
      });

      if (obsInstalled) {
        // インストール済みの場合は必ず状態を更新
        await markSubstepCompleted(
          InstallationStep.OBS_SETUP,
          setupSteps[0].id,
          true,
        );
        console.log("[OBSSetup] Marked OBS as completed");
      } else if (showError) {
        // ユーザーがチェックを入れようとした場合のみエラー表示
        alert(
          "OBS Studio が検出されませんでした。インストールしてからチェックを入れてください。",
        );
      }
    } catch (error) {
      console.error("OBS check failed", error);
      if (showError) {
        alert("OBSの確認中にエラーが発生しました。");
      }
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function checkNDIInstallation(
    showError: boolean = false,
  ): Promise<void> {
    isChecking = true;
    checkingIndex = 2;
    try {
      const result: SystemCheckResult = await checkSystem("ndi");
      ndiInstalled = result.is_installed;
      ndiVersion = result.version || null;
      ndiPath = result.installation_path || null;

      console.log("[OBSSetup] NDI check result:", {
        ndiInstalled,
        ndiVersion,
        ndiPath,
        currentCompleted: setupSteps[2]?.completed,
      });

      if (ndiInstalled) {
        // インストール済みの場合は必ず状態を更新
        await markSubstepCompleted(
          InstallationStep.OBS_SETUP,
          setupSteps[2].id,
          true,
        );
        console.log("[OBSSetup] Marked NDI as completed");
      } else if (showError) {
        // ユーザーがチェックを入れようとした場合のみエラー表示
        alert(
          "NDI Runtime が検出されませんでした。インストールしてからチェックを入れてください。",
        );
      }
    } catch (error) {
      console.warn("NDI Runtime check failed:", error);
      if (showError) {
        alert("NDI Runtimeの確認中にエラーが発生しました。");
      }
    } finally {
      isChecking = false;
      checkingIndex = null;
    }
  }

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    // OBSインストール確認
    if (index === 0) {
      await checkOBSInstallation(true);
      return;
    }

    // NDI Runtimeインストール確認
    if (index === 2) {
      await checkNDIInstallation(true);
      return;
    }

    // その他のステップは通常通りトグル
    await markSubstepCompleted(
      InstallationStep.OBS_SETUP,
      step.id,
      !step.completed,
    );
  }

  function openUrl(url: string): void {
    window.open(url, "_blank");
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
      (target.closest("button") ||
        target.closest("a") ||
        target.closest("input"))
    ) {
      return;
    }

    toggleStep(currentSubStepIndex);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      handleCardClick(event);
    }
  }

  function isStepAutoCompleted(index: number): boolean {
    return (index === 0 && obsInstalled) || (index === 2 && ndiInstalled);
  }

  function isStepChecked(index: number): boolean {
    // 手順1(OBS)と手順3(NDI)はAPIの結果を優先
    if (index === 0) {
      console.log("[OBSSetup] isStepChecked(0):", obsInstalled);
      return obsInstalled;
    }
    if (index === 2) {
      console.log("[OBSSetup] isStepChecked(2):", ndiInstalled);
      return ndiInstalled;
    }
    // その他の手順はtomlの状態を使用
    const completed = setupSteps[index]?.completed || false;
    console.log(`[OBSSetup] isStepChecked(${index}):`, completed);
    return completed;
  }
</script>

<div class="obs-setup">
  <div class="step-header">
    <h2 class="step-title">OBS Studio セットアップ</h2>
    <p class="step-description">
      ゲーム映像を録画するため、OBS Studio
      と必要なプラグインをインストールし、録画設定を行います
    </p>
  </div>

  <div class="setup-steps-section">
    <div
      class="step-card glass-card"
      class:completed={currentStepChecked}
      class:disabled={isStepAutoCompleted(currentSubStepIndex)}
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
                {#if (currentSubStepIndex === 0 && obsInstalled) || (currentSubStepIndex === 2 && ndiInstalled)}
                  <span class="installed-badge">インストール済</span>
                {/if}
              </div>
            </div>
            <div class="checkbox-indicator" class:checked={currentStepChecked}>
              {#if currentStepChecked}
                <Check size={20} />
              {/if}
            </div>
          </div>

          <div class="card-body">
            {#if currentSubStepIndex === 0}
              <!-- OBS Install -->
              <ol class="instruction-list">
                <li>
                  OBS Studio 公式サイトから最新版をダウンロードします
                  <div style="margin-top: 1rem;">
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
                <li>ダウンロードしたインストーラーを実行します</li>
              </ol>
            {:else if currentSubStepIndex === 1}
              <!-- OBS NDI Plugin -->
              <ol class="instruction-list">
                <li>
                  GitHubの「Releases」ページから最新版(Latest)を探す
                  <div style="margin-top: 1rem;">
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
                  「Assets」エリアから「Windows-x64-installer.exe」をダウンロードします
                </li>
                <li>ダウンロードしたインストーラーを実行します</li>
              </ol>
            {:else if currentSubStepIndex === 2}
              <!-- NDI Runtime -->
              <ol class="instruction-list">
                <li>
                  NDI 公式サイトにアクセス
                  <div style="margin-top: 1rem;">
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
                <li>「Download (.msi)」のリンクをクリックします</li>
                <li>NDI Runtimeをダウンロードしてインストールを完了します</li>
              </ol>
              <p class="step-note">
                ※ NDI
                Runtimeをインストールする前にOBSを起動するとエラーが表示されます
              </p>
            {:else if currentSubStepIndex === 3}
              <!-- Capture Device -->
              <ol class="instruction-list">
                <li>OBSを起動します</li>
                <li>OBSの「ソース」パネルの「+」ボタンをクリックします</li>
                <li>「映像キャプチャデバイス」を選択します</li>
                <li>キャプチャーデバイスを選択します</li>
                <li>OKボタンをクリックして設定画面を閉じます</li>
                <li>映像が表示されていることを確認します</li>
              </ol>
            {:else if currentSubStepIndex === 4}
              <!-- NDI Settings -->
              <ol class="instruction-list">
                <li>
                  OBS の「ツール」メニューから「DistroAV NDI
                  Settings」をクリックします
                </li>
                <li>「Main Output」にチェックを入れます</li>
                <li>OKボタンをクリックして設定画面を閉じます</li>
              </ol>
            {:else if currentSubStepIndex === 5}
              <!-- Recording Settings -->
              <p style="margin: 0.5rem 0 0 0; font-weight: 600;">推奨設定:</p>
              <ol class="instruction-list">
                <li>フォーマット: MKV</li>
                <li>解像度: 1920x1080 (1080p)</li>
                <li>フレームレート: 30 FPS 以上</li>
                <li>エンコーダ: ハードウェアエンコーダ(H.264やHEVC等)推奨</li>
              </ol>
              <p class="step-note">
                ※
                一度録画をしてみて、映像のカクツキや音声の乱れがないか確認することを推奨します。
              </p>
            {/if}
          </div>
        </div>
      {/key}
    </div>
  </div>
</div>

<style>
  .obs-setup {
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

  .step-note {
    margin: 1rem 0 0 0;
    font-size: 0.85rem;
    font-style: italic;
    color: var(--text-secondary);
  }

  .icon {
    display: block;
    flex-shrink: 0;
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
