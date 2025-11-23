<script lang="ts">
  import { onMount } from "svelte";
  import {
    Download,
    ExternalLink,
    FolderOpen,
    Key,
    AlertCircle,
    RefreshCw,
    Check,
  } from "lucide-svelte";
  import {
    checkSystem,
    markSubstepCompleted,
    installationState,
  } from "../../store";
  import { type SystemCheckResult, InstallationStep } from "../../types";

  let credentialsInstalled = false;
  let checkingIndex: number | null = null;

  let setupCompleted = {
    createProject: false,
    enableAPI: false,
    createCredentials: false,
    downloadJSON: false,
    placeFile: false,
  };

  onMount(async () => {
    await checkYouTubeCredentials();
  });

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.YOUTUBE_SETUP] || {};
    setupCompleted = {
      createProject: details["youtube-create-project"] || false,
      enableAPI: details["youtube-enable-api"] || false,
      createCredentials: details["youtube-create-credentials"] || false,
      downloadJSON: details["youtube-download-json"] || false,
      placeFile: details["youtube-place-file"] || false,
    };
  }

  async function checkYouTubeCredentials(): Promise<void> {
    try {
      const result: SystemCheckResult = await checkSystem("youtube");
      credentialsInstalled = result.is_installed;

      if (credentialsInstalled) {
        // ファイルが存在する場合、全ステップにチェックを入れる
        const steps = [
          "youtube-create-project",
          "youtube-enable-api",
          "youtube-create-credentials",
          "youtube-download-json",
          "youtube-place-file",
        ];
        for (const stepId of steps) {
          await markSubstepCompleted(
            InstallationStep.YOUTUBE_SETUP,
            stepId,
            true,
          );
        }
      }
    } catch (error) {
      console.error("YouTube credentials check failed:", error);
    }
  }

  async function toggleStep(
    step: keyof typeof setupCompleted,
    index: number,
  ): Promise<void> {
    const currentValue = setupCompleted[step];
    const stepIds: Record<keyof typeof setupCompleted, string> = {
      createProject: "youtube-create-project",
      enableAPI: "youtube-enable-api",
      createCredentials: "youtube-create-credentials",
      downloadJSON: "youtube-download-json",
      placeFile: "youtube-place-file",
    };
    const stepId = stepIds[step];

    // 手順5（placeFile）のチェック時にファイル存在確認
    if (step === "placeFile" && !currentValue) {
      checkingIndex = index;
      try {
        const result: SystemCheckResult = await checkSystem("youtube");
        if (result.is_installed) {
          // ファイルが存在する場合、全ステップにチェックを入れる
          credentialsInstalled = true;
          const steps = [
            "youtube-create-project",
            "youtube-enable-api",
            "youtube-create-credentials",
            "youtube-download-json",
            "youtube-place-file",
          ];
          for (const sId of steps) {
            await markSubstepCompleted(
              InstallationStep.YOUTUBE_SETUP,
              sId,
              true,
            );
          }
        } else {
          // ファイルが存在しない場合、通知してチェックを入れない
          alert("client_secrets.json ファイルが見つかりませんでした。");
        }
      } catch (error) {
        console.error("YouTube credentials check failed:", error);
        alert("認証情報の確認に失敗しました。");
      } finally {
        checkingIndex = null;
      }
      return;
    }

    // インストール済の場合はチェックを外せないようにする
    if (credentialsInstalled && currentValue) {
      return;
    }

    // 通常のトグル
    await markSubstepCompleted(
      InstallationStep.YOUTUBE_SETUP,
      stepId,
      !currentValue,
    );
  }

  function openUrl(url: string): void {
    window.open(url, "_blank");
  }
</script>

<div class="youtube-setup">
  <div class="step-header">
    <h2 class="step-title">YouTube API 設定</h2>
    <p class="step-description">
      YouTube への自動アップロード機能を使用するために、 YouTube Data API
      を有効化し、認証情報を設定します。
    </p>
  </div>

  <div class="warning-card glass-card">
    <AlertCircle class="icon" size={24} />
    <div class="warning-content">
      <h3 class="warning-title">重要な注意事項</h3>
      <p class="warning-text">
        YouTube API の使用には Google アカウントが必要です。 また、API
        の利用には Google Cloud Platform のプロジェクト作成が必要です。
        無料枠内での使用が可能ですが、クレジットカード情報の登録が求められる場合があります。
      </p>
    </div>
  </div>

  <div class="setup-steps-section">
    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">1</div>
        <div class="step-info">
          <h4 class="step-name">
            Google Cloud プロジェクトの作成
            {#if credentialsInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupCompleted.createProject}
            <div class="instructions">
              <ol>
                <li>
                  新しいプロジェクト作成ページにアクセスする
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://console.cloud.google.com/projectcreate",
                        )}
                    >
                      <ExternalLink class="icon" size={16} />
                      新しいプロジェクトを作成する
                    </button>
                  </div>
                </li>
                <li>プロジェクト名を入力する（例: Splat Replay）</li>
                <li>「作成」をクリック</li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupCompleted.createProject}
          on:click={() => toggleStep("createProject", 0)}
          aria-label={setupCompleted.createProject
            ? "完了を解除"
            : "完了にする"}
          disabled={credentialsInstalled}
        >
          <div
            class="checkbox-box"
            class:checked={setupCompleted.createProject}
          >
            {#if setupCompleted.createProject}
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
            YouTube Data API v3 の有効化
            {#if credentialsInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupCompleted.enableAPI}
            <div class="instructions">
              <ol>
                <li>
                  YouTube Data API v3 の有効化ページを開く
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://console.cloud.google.com/apis/library/youtube.googleapis.com",
                        )}
                    >
                      <ExternalLink class="icon" size={16} />
                      YouTube Data API を開く
                    </button>
                  </div>
                </li>
                <li>
                  ページ上部に表示されているプロジェクト名を確認し、正しく選択されていることを確認する
                </li>
                <li>「有効にする」ボタンをクリックする</li>
                <li>API が有効になるまで待機する</li>
              </ol>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupCompleted.enableAPI}
          on:click={() => toggleStep("enableAPI", 1)}
          aria-label={setupCompleted.enableAPI ? "完了を解除" : "完了にする"}
          disabled={credentialsInstalled}
        >
          <div class="checkbox-box" class:checked={setupCompleted.enableAPI}>
            {#if setupCompleted.enableAPI}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">3</div>
        <div class="step-info">
          <h4 class="step-name">
            OAuth 2.0 認証情報の作成
            {#if credentialsInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupCompleted.createCredentials}
            <div class="instructions">
              <ol>
                <li>
                  認証情報ページを開く
                  <div style="margin-top: 0.5rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          "https://console.cloud.google.com/apis/credentials",
                        )}
                    >
                      <Key class="icon" size={16} />
                      認証情報ページを開く
                    </button>
                  </div>
                </li>
                <li>
                  ページ上部に表示されているプロジェクト名を確認し、正しく選択されていることを確認する
                </li>
                <li>
                  「同意画面を構成」ボタンがある場合、「同意画面を構成」をクリックし、アプリ名・メールアドレス等を入力し、作成ボタンをクリックする
                </li>
                <li>「認証情報を作成」→「OAuth クライアント ID」を選択</li>
                <li>アプリケーションの種類: 「デスクトップ アプリ」を選択</li>
                <li>名前を入力する（例: Splat Replay）</li>
                <li>「作成」をクリックする</li>
                <li>JSONをダウンロードをクリックする</li>
              </ol>
            </div>
            <div class="info-box">
              <p>
                ※ 初回作成時は「OAuth 同意画面」の設定が必要な場合があります。
                その場合は画面の指示に従って設定してください。
              </p>
            </div>
          {/if}
        </div>
        <button
          class="step-checkbox"
          type="button"
          class:checked={setupCompleted.createCredentials}
          on:click={() => toggleStep("createCredentials", 2)}
          aria-label={setupCompleted.createCredentials
            ? "完了を解除"
            : "完了にする"}
          disabled={credentialsInstalled}
        >
          <div
            class="checkbox-box"
            class:checked={setupCompleted.createCredentials}
          >
            {#if setupCompleted.createCredentials}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <div class="step-card glass-card">
      <div class="step-content">
        <div class="step-number">5</div>
        <div class="step-info">
          <h4 class="step-name">
            認証情報ファイルの配置
            {#if credentialsInstalled}
              <span class="installed-badge">インストール済</span>
            {/if}
          </h4>
          {#if !setupCompleted.placeFile}
            <div class="instructions">
              <ol>
                <li>ファイル名を <code>client_secrets.json</code> に変更</li>
                <li>
                  アプリケーションの config フォルダに <code
                    >client_secrets.json</code
                  >
                  ファイルを配置
                  <div class="path-box">
                    <FolderOpen class="icon" size={20} />
                    <div class="path-content">
                      <p class="path-label">配置先フォルダ:</p>
                      <code class="path-value">config/client_secrets.json</code>
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
          class:checked={setupCompleted.placeFile}
          on:click={() => toggleStep("placeFile", 4)}
          aria-label={setupCompleted.placeFile ? "完了を解除" : "完了にする"}
          disabled={credentialsInstalled || checkingIndex === 4}
        >
          <div class="checkbox-box" class:checked={setupCompleted.placeFile}>
            {#if checkingIndex === 4}
              <RefreshCw class="icon spinning" size={20} />
            {:else if setupCompleted.placeFile}
              <Check class="check-icon" size={20} />
            {/if}
          </div>
        </button>
      </div>
    </div>

    <div class="info-card glass-card">
      <div class="info-card-content">
        <h4 class="info-card-title">初回認証について</h4>
        <p class="info-card-text">
          アプリケーションから YouTube への初回アップロード時に、
          ブラウザが開いて認証画面が表示されます。 Google
          アカウントでログインし、アクセスを許可してください。
        </p>
        <p class="info-card-text">
          認証が完了すると、トークンファイルが自動的に保存され、
          次回以降は自動的にアップロードが行われます。
        </p>
      </div>
    </div>
  </div>
</div>

<style>
  .youtube-setup {
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

  .installation-check {
    padding: 1.5rem;
  }

  .check-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .check-title {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .refresh-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .refresh-button:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }

  .refresh-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .check-status {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.25rem;
    border-radius: 8px;
    border: 1px solid;
  }

  .check-status.checking {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .check-status.success {
    background: rgba(25, 211, 199, 0.1);
    border-color: rgba(25, 211, 199, 0.3);
  }

  .check-status.error,
  .check-status.not-found {
    background: rgba(255, 107, 107, 0.1);
    border-color: rgba(255, 107, 107, 0.3);
  }

  .status-icon {
    flex-shrink: 0;
  }

  .check-status.success .status-icon {
    color: var(--accent-color);
  }

  .check-status.error .status-icon,
  .check-status.not-found .status-icon {
    color: #ff6b6b;
  }

  .status-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .status-text {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .status-detail,
  .error-message {
    margin: 0;
    font-size: 0.875rem;
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

  .warning-card {
    padding: 1.5rem;
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    background: rgba(255, 165, 0, 0.05);
    border-color: rgba(255, 165, 0, 0.3);
  }

  .warning-card > .icon {
    flex-shrink: 0;
    color: #ffa500;
    margin-top: 0.125rem;
  }

  .warning-content {
    flex: 1;
  }

  .warning-title {
    margin: 0 0 0.5rem 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .warning-text {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  .info-card {
    padding: 1.5rem;
    background: rgba(25, 211, 199, 0.05);
    border-color: rgba(25, 211, 199, 0.3);
  }

  .info-card-content {
    flex: 1;
  }

  .info-card-title {
    margin: 0 0 0.75rem 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--accent-color);
  }

  .info-card-text {
    margin: 0 0 0.5rem 0;
    font-size: 0.9375rem;
    line-height: 1.6;
    color: var(--text-secondary);
    text-align: left;
  }

  .info-card-text:last-child {
    margin-bottom: 0;
  }

  .setup-steps-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .section-title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--accent-color);
    text-transform: uppercase;
    letter-spacing: 0.05em;
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
    text-align: left;
  }

  .step-desc {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: var(--text-secondary);
    white-space: pre-line;
    text-align: left;
  }

  .step-desc code {
    padding: 0.125rem 0.375rem;
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
    font-size: 0.875rem;
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
    .youtube-setup {
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
