<script lang="ts">
  import { onMount } from 'svelte';
  import { SetupApp } from './setup';
  import { setupState, fetchInstallationStatus } from './setup/stores/state';
  import MainApp from './main/MainApp.svelte';
  import { initializeRenderMode, setRenderMode } from './main/renderMode';

  let isCheckingInstallation = $state(true);

  async function refreshInstallationStatus(): Promise<void> {
    isCheckingInstallation = true;
    setupState.set(null);
    try {
      await fetchInstallationStatus();
    } finally {
      isCheckingInstallation = false;
    }
  }

  onMount(async () => {
    setRenderMode('cpu');
    const renderModePromise = initializeRenderMode();

    // インストール状態をチェック
    await refreshInstallationStatus();

    await renderModePromise;
  });

  const hasKnownServerPlatform = $derived(
    $setupState?.server_platform === 'windows' || $setupState?.server_platform === 'macos'
  );
  const showSetup = $derived(
    !isCheckingInstallation && $setupState?.is_completed === false && hasKnownServerPlatform
  );
  const showMainApp = $derived(!isCheckingInstallation && $setupState?.is_completed === true);
  const showSetupStatusUnavailable = $derived(
    !isCheckingInstallation && !showSetup && !showMainApp
  );
</script>

{#if isCheckingInstallation}
  <div class="loading-screen">
    <div class="loading-spinner"></div>
    <p>読み込み中...</p>
  </div>
{:else if showSetup}
  <SetupApp />
{:else if showMainApp}
  <MainApp />
{:else if showSetupStatusUnavailable}
  <div class="setup-status-unavailable" role="alert">
    <p>サーバーのOS情報を確認できません。通信状況を確認して、もう一度お試しください。</p>
    <button class="button button-primary" type="button" onclick={refreshInstallationStatus}>
      再試行
    </button>
  </div>
{/if}

<style>
  .loading-screen {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.5rem;
  }

  .loading-spinner {
    width: 64px;
    height: 64px;
    border: 4px solid rgba(var(--theme-rgb-white), 0.1);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    box-shadow:
      0 0 0 1px rgba(var(--theme-rgb-white), 0.06) inset,
      0 0 16px rgba(var(--theme-rgb-accent), 0.12);
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .loading-screen p {
    margin: 0;
    font-size: 1.125rem;
    color: var(--text-secondary);
  }

  .setup-status-unavailable {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
  }

  .setup-status-unavailable p {
    margin: 0;
    color: var(--text-secondary);
    text-align: center;
  }
</style>
