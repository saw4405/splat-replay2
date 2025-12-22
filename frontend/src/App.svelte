<script lang="ts">
  import { onMount } from 'svelte';
  import { InstallerApp } from './installer';
  import { installationState, fetchInstallationStatus } from './installer/store';
  import MainApp from './main/MainApp.svelte';

  let isCheckingInstallation = true;

  onMount(async () => {
    // インストール状態をチェック
    await fetchInstallationStatus();
    isCheckingInstallation = false;
  });

  $: showInstaller =
    !isCheckingInstallation && (!$installationState || !$installationState.is_completed);
  $: showMainApp = !isCheckingInstallation && $installationState && $installationState.is_completed;
</script>

{#if isCheckingInstallation}
  <div class="loading-screen">
    <div class="loading-spinner"></div>
    <p>読み込み中...</p>
  </div>
{:else if showInstaller}
  <InstallerApp />
{:else if showMainApp}
  <MainApp />
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
    border: 4px solid rgba(255, 255, 255, 0.1);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
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
</style>
