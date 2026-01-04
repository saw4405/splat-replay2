<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { ExternalLink, FolderOpen, Key, AlertCircle, Check } from 'lucide-svelte';
  import { checkSystem } from '../../stores/system';
  import { markSubstepCompleted } from '../../stores/navigation';
  import { saveYouTubePrivacyStatus } from '../../stores/config';
  import { setupState } from '../../stores/state';
  import { type SystemCheckResult, SetupStep } from '../../types';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';

  const SUBSTEP_STORAGE_KEY = 'youtube_substep_index';

  interface SetupStep {
    id: string;
    title: string;
    description: string;
    completed: boolean;
  }

  const dispatch = createEventDispatcher<{
    substepChange: { isFinalSubstep: boolean };
  }>();

  let credentialsInstalled = false;
  let isChecking = false;
  let hasInitializedSubstep = false;
  let dialogOpen = false;
  let dialogMessage = '';
  let dialogVariant: 'info' | 'success' | 'warning' | 'error' = 'info';
  let privacyStatus: 'public' | 'unlisted' | 'private' = 'private';

  let setupSteps: SetupStep[] = [
    {
      id: 'youtube-create-project',
      title: 'Google Cloud プロジェクトの作成',
      description: 'YouTube API を使用するための Google Cloud プロジェクトを作成します。',
      completed: false,
    },
    {
      id: 'youtube-enable-api',
      title: 'YouTube Data API v3 の有効化',
      description: '作成したプロジェクトで YouTube Data API を有効化します。',
      completed: false,
    },
    {
      id: 'youtube-configure-consent',
      title: 'OAuth 同意画面の構成',
      description: 'OAuth 認証に必要な同意画面を構成します。',
      completed: false,
    },
    {
      id: 'youtube-create-credentials',
      title: 'OAuth 認証情報の作成',
      description: 'YouTube API にアクセスするための認証情報を作成します。',
      completed: false,
    },
    {
      id: 'youtube-place-file',
      title: '認証情報ファイルの配置',
      description: 'ダウンロードした認証情報ファイルをアプリケーションフォルダに配置します。',
      completed: false,
    },
    {
      id: 'youtube-account-verification',
      title: 'アカウント認証',
      description: '15分以上の動画をアップロードするためにアカウントを認証します。',
      completed: false,
    },
    {
      id: 'youtube-privacy-status',
      title: '動画の公開範囲設定',
      description: 'アップロードする動画のデフォルトの公開範囲を設定します。',
      completed: false,
    },
  ];

  let currentSubStepIndex = 0;
  let isOnFinalSubstep = false;

  // 親コンポーネントに通知するためのフラグ
  export let canGoBack = false;
  export let isStepCompleted = false;

  $: isStepCompleted = setupSteps[currentSubStepIndex].completed;

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
    const firstIncomplete = _steps.findIndex((step) => !step.completed);
    if (firstIncomplete !== -1) {
      return firstIncomplete;
    }
    return _steps.length > 0 ? _steps.length - 1 : 0;
  }

  $: {
    isOnFinalSubstep = currentSubStepIndex >= setupSteps.length - 1;
    dispatch('substepChange', { isFinalSubstep: isOnFinalSubstep });
  }

  $: canGoBack = currentSubStepIndex > 0;

  // 現在のステップが変更されたときにhasInitializedSubstepをリセット
  $: if ($setupState?.current_step !== SetupStep.YOUTUBE_SETUP) {
    hasInitializedSubstep = false;
  }

  // Sync with installation state
  $: if ($setupState && $setupState.step_details) {
    const details = $setupState.step_details[SetupStep.YOUTUBE_SETUP] || {};
    const updatedSteps = setupSteps.map((step, index) => ({
      ...step,
      // 手順1〜5（インデックス0〜4）は credentialsInstalled も考慮
      // 手順6,7（インデックス5,6）は details のみから状態を取得
      completed: index <= 4 ? details[step.id] || credentialsInstalled : details[step.id] || false,
    }));
    setupSteps = updatedSteps;

    if (!hasInitializedSubstep && $setupState.current_step === SetupStep.YOUTUBE_SETUP) {
      // ステップに入った時に認証情報ファイルの有無をチェック
      checkSystem('youtube')
        .then((result: SystemCheckResult) => {
          if (result.is_installed) {
            credentialsInstalled = true;
          }
        })
        .catch((error) => {
          console.error('Initial YouTube credentials check failed:', error);
        });

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

  export async function next(_options: { skip?: boolean } = {}): Promise<boolean> {
    const currentStep = setupSteps[currentSubStepIndex];

    // ファイル配置ステップのバリデーション
    if (currentSubStepIndex === 4) {
      isChecking = true;
      try {
        const result: SystemCheckResult = await checkSystem('youtube');
        if (result.is_installed) {
          // ファイルが存在する場合、手順1〜5を完了とする
          credentialsInstalled = true;
          for (let i = 0; i <= 4; i++) {
            await markSubstepCompleted(SetupStep.YOUTUBE_SETUP, setupSteps[i].id, true);
          }
        } else {
          showDialog(
            'client_secret.json ファイルが見つかりませんでした。配置してから次へ進んでください。',
            'warning'
          );
          isChecking = false;
          return true;
        }
      } catch (error) {
        console.error('YouTube credentials check failed:', error);
        showDialog('認証情報の確認に失敗しました。', 'error');
        isChecking = false;
        return true;
      } finally {
        isChecking = false;
      }
    }

    // 手順7（公開範囲設定）の保存
    if (currentSubStepIndex === 6) {
      try {
        await saveYouTubePrivacyStatus(privacyStatus);
        await markSubstepCompleted(SetupStep.YOUTUBE_SETUP, currentStep.id, true);
      } catch (error) {
        console.error('Failed to save privacy status:', error);
        showDialog('公開範囲の保存に失敗しました。', 'error');
        return true;
      }
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

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    // 手順5(インデックス4、ファイル配置)の場合のみ、チェック時にファイル存在確認を行う
    if (index === 4) {
      // インストール済の場合はチェックを外せないようにする
      if (credentialsInstalled && step.completed) return;

      if (!step.completed) {
        isChecking = true;
        try {
          const result: SystemCheckResult = await checkSystem('youtube');
          if (result.is_installed) {
            // ファイルが存在する場合、手順1〜5(インデックス0〜4)を完了とする
            credentialsInstalled = true;
            for (let i = 0; i <= 4; i++) {
              await markSubstepCompleted(SetupStep.YOUTUBE_SETUP, setupSteps[i].id, true);
            }
          } else {
            // ファイルが存在しない場合、エラーダイアログを表示してチェックを入れない
            showDialog('client_secret.json ファイルが見つかりませんでした。', 'warning');
          }
        } catch (error) {
          console.error('YouTube credentials check failed:', error);
          showDialog('認証情報の確認に失敗しました。', 'error');
        } finally {
          isChecking = false;
        }
      } else {
        // 手順5を未完了に戻す(インストール済でない場合のみここに来る)
        await markSubstepCompleted(SetupStep.YOUTUBE_SETUP, step.id, false);
      }
    } else if (index <= 3) {
      // 手順1〜4 (インデックス0〜3) はファイル確認せずに単純にトグルする
      // インストール済の場合はチェックを外せないようにする
      if (credentialsInstalled && step.completed) return;

      await markSubstepCompleted(SetupStep.YOUTUBE_SETUP, step.id, !step.completed);
    } else {
      // 手順6,7 (インデックス5,6) は認証情報ファイルの有無に関係なく独立して管理
      await markSubstepCompleted(SetupStep.YOUTUBE_SETUP, step.id, !step.completed);
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

<div class="youtube-setup">
  <div class="step-header">
    <div class="title-row">
      <h2 class="step-title">YouTube API 設定</h2>
      <div class="tooltip-container">
        <AlertCircle class="icon warning-icon" size={20} />
        <div class="tooltip-content glass-card">
          <p>
            YouTube API の使用には Google アカウントが必要です。 また、API の利用には Google Cloud
            Platform のプロジェクト作成が必要です。
            無料枠内での使用が可能ですが、クレジットカード情報の登録が求められる場合があります。
          </p>
        </div>
      </div>
    </div>
    <p class="step-description">
      YouTube への自動アップロード機能を使用するために、 YouTube Data API
      を有効化し、認証情報を設定します
    </p>
  </div>

  <div class="setup-steps-section">
    <div
      class="step-card glass-card"
      class:completed={setupSteps[currentSubStepIndex].completed}
      class:disabled={(credentialsInstalled && currentSubStepIndex <= 4) ||
        (currentSubStepIndex === 4 && isChecking)}
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
                {#if credentialsInstalled && currentSubStepIndex <= 4}
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
              <!-- Create Project -->
              <ol class="instruction-list">
                <li>
                  新しいプロジェクト作成ページにアクセスします
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() => openUrl('https://console.cloud.google.com/projectcreate')}
                    >
                      <ExternalLink class="icon" size={16} />
                      新しいプロジェクトを作成します
                    </button>
                  </div>
                </li>
                <li>プロジェクト名を入力します（例: Splat Replay）</li>
                <li>「作成」をクリックします</li>
              </ol>
            {:else if currentSubStepIndex === 1}
              <!-- Enable API -->
              <ol class="instruction-list">
                <li>
                  YouTube Data API v3 の有効化ページを開きます
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl(
                          'https://console.cloud.google.com/apis/library/youtube.googleapis.com'
                        )}
                    >
                      <ExternalLink class="icon" size={16} />
                      YouTube Data API を開く
                    </button>
                  </div>
                </li>
                <li>
                  ページ上部に表示されているプロジェクト名を確認し、正しく選択されていることを確認します
                </li>
                <li>「有効にする」ボタンをクリックします</li>
                <li>API が有効になるまで待機します</li>
              </ol>
            {:else if currentSubStepIndex === 2}
              <!-- Configure OAuth Consent Screen -->
              <ol class="instruction-list">
                <li>
                  OAuth 同意画面の設定ページを開く
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() =>
                        openUrl('https://console.cloud.google.com/apis/credentials/consent')}
                    >
                      <ExternalLink class="icon" size={16} />
                      OAuth 同意画面を開く
                    </button>
                  </div>
                </li>
                <li>
                  ページ上部に表示されているプロジェクト名を確認し、正しく選択されていることを確認します
                </li>
                <li>「開始」ボタンをクリックします</li>
                <li>
                  アプリ情報を入力します
                  <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                    <li>アプリ名: 任意の名前（例: Splat Replay）</li>
                    <li>ユーザーサポートメール: 自分のメールアドレスを選択</li>
                    <li>対象: 外部</li>
                    <li>デベロッパーの連絡先情報: 自分のメールアドレスを入力</li>
                  </ul>
                </li>
                <li>「作成」をクリックします</li>
                <li>「対象」セクションを選択します</li>
                <li>テストユーザーの「Add Users」をクリックします</li>
                <li>自分のメールアドレスを入力し、保存ボタンをクリックします</li>
              </ol>
            {:else if currentSubStepIndex === 3}
              <!-- Create Credentials -->
              <ol class="instruction-list">
                <li>
                  認証情報ページを開く
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() => openUrl('https://console.cloud.google.com/apis/credentials')}
                    >
                      <Key class="icon" size={16} />
                      認証情報ページを開く
                    </button>
                  </div>
                </li>
                <li>
                  ページ上部に表示されているプロジェクト名を確認し、正しく選択されていることを確認します
                </li>
                <li>「認証情報を作成」→「OAuth クライアント ID」を選択します</li>
                <li>アプリケーションの種類: 「デスクトップ アプリ」を選択します</li>
                <li>名前を入力します（例: Splat Replay）</li>
                <li>「作成」をクリックします</li>
                <li>JSONをダウンロードをクリックします</li>
              </ol>
            {:else if currentSubStepIndex === 4}
              <!-- Place File -->
              <ol class="instruction-list">
                <li>
                  ファイル名を <code>client_secret.json</code> に変更します
                </li>
                <li>
                  アプリケーションの config フォルダに <code>client_secret.json</code>
                  ファイルを配置します
                  <div class="path-box">
                    <FolderOpen class="icon" size={20} />
                    <div class="path-content">
                      <code class="path-value">SplatReplay\config</code>
                    </div>
                  </div>
                </li>
              </ol>
            {:else if currentSubStepIndex === 5}
              <!-- Account Verification -->
              <p style="margin-bottom: 1rem;">
                15分以上の動画をアップロードするには、YouTubeアカウントの認証が必要です。
              </p>
              <ol class="instruction-list">
                <li>
                  YouTube アカウント認証ページにアクセスします
                  <div style="margin-top: 1rem;">
                    <button
                      class="link-button"
                      type="button"
                      on:click={() => openUrl('https://www.youtube.com/verify')}
                    >
                      <ExternalLink class="icon" size={16} />
                      アカウント認証ページを開く
                    </button>
                  </div>
                </li>
                <li>画面の指示に従って、電話番号による認証を完了してください。</li>
                <li>認証が完了すると、15分以上の動画をアップロードできるようになります。</li>
              </ol>
              <div
                class="info-note"
                style="margin-top: 1rem; padding: 0.75rem; background: rgba(25, 211, 199, 0.1); border: 1px solid rgba(25, 211, 199, 0.3); border-radius: 8px;"
              >
                <p style="margin: 0; font-size: 0.875rem; color: var(--text-secondary);">
                  <strong style="color: var(--accent-color);">注意:</strong> この認証は、Google Cloud
                  の認証とは別のものです。YouTubeアカウント自体の認証が必要です。
                </p>
              </div>
            {:else if currentSubStepIndex === 6}
              <!-- Privacy Status -->
              <p style="margin: 0 0 1rem 0; font-size: 0.9rem; color: var(--text-secondary);">
                アップロードする動画のデフォルトの公開範囲を選択してください
              </p>
              <div class="privacy-options">
                <label class="privacy-option">
                  <input
                    type="radio"
                    name="privacy"
                    value="private"
                    bind:group={privacyStatus}
                    on:click={(e) => e.stopPropagation()}
                  />
                  <div class="option-content">
                    <div class="option-title">非公開</div>
                    <div class="option-description">自分だけが視聴できます</div>
                  </div>
                </label>
                <label class="privacy-option">
                  <input
                    type="radio"
                    name="privacy"
                    value="unlisted"
                    bind:group={privacyStatus}
                    on:click={(e) => e.stopPropagation()}
                  />
                  <div class="option-content">
                    <div class="option-title">限定公開</div>
                    <div class="option-description">リンクを知っている人が視聴できます</div>
                  </div>
                </label>
                <label class="privacy-option">
                  <input
                    type="radio"
                    name="privacy"
                    value="public"
                    bind:group={privacyStatus}
                    on:click={(e) => e.stopPropagation()}
                  />
                  <div class="option-content">
                    <div class="option-title">公開</div>
                    <div class="option-description">誰でも検索して視聴できます</div>
                  </div>
                </label>
              </div>
            {/if}
          </div>
        </div>
      {/key}
    </div>
  </div>
</div>

<NotificationDialog
  isOpen={dialogOpen}
  variant={dialogVariant}
  message={dialogMessage}
  on:close={() => (dialogOpen = false)}
/>

<style>
  .youtube-setup {
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

  .title-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .tooltip-container {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: help;
  }

  .tooltip-content {
    visibility: hidden;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%) translateY(-10px);
    width: 320px;
    padding: 1rem;
    background: rgba(20, 20, 20, 0.95);
    border: 1px solid rgba(255, 165, 0, 0.3);
    border-radius: 8px;
    z-index: 100;
    opacity: 0;
    transition: all 0.2s ease;
    pointer-events: none;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(10px);
  }

  .tooltip-container:hover .tooltip-content {
    visibility: visible;
    opacity: 1;
    transform: translateX(-50%) translateY(-5px);
  }

  .tooltip-content p {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.6;
    color: #e0e0e0;
    text-align: left;
  }

  /* Tooltip arrow */
  .tooltip-content::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -6px;
    border-width: 6px;
    border-style: solid;
    border-color: rgba(255, 165, 0, 0.3) transparent transparent transparent;
  }

  .setup-steps-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    gap: 1rem;
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

  .privacy-options {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .privacy-option {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.03);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .privacy-option:hover {
    border-color: rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.05);
  }

  .privacy-option input[type='radio'] {
    margin-top: 0.125rem;
    cursor: pointer;
    width: 18px;
    height: 18px;
    accent-color: var(--accent-color);
  }

  .option-content {
    flex: 1;
  }

  .option-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
  }

  .option-description {
    font-size: 0.875rem;
    color: var(--text-secondary);
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
