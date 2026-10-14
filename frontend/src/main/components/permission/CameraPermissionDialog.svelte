<script lang="ts">
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import { getClientPlatform } from '../../../setup/platform';

  interface Props {
    open?: boolean;
  }

  let { open = $bindable(false) }: Props = $props();
  const clientPlatform = getClientPlatform();

  let dontShowAgain = $state(false);

  async function handleClose(): Promise<void> {
    if (dontShowAgain) {
      try {
        await fetch('/api/settings/camera-permission-dialog', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shown: true }),
        });
      } catch (error) {
        console.error('Failed to save camera permission dialog state:', error);
      }
    }
    open = false;
  }
</script>

<BaseDialog
  bind:open
  footerVariant="compact"
  primaryButtonText="閉じる"
  maxWidth="32rem"
  minHeight="auto"
  onPrimaryClick={handleClose}
>
  {#snippet header()}
    <h2 id="dialog-title">カメラ入力の許可</h2>
  {/snippet}

  <div class="dialog-content">
    <div class="info-section">
      <p class="message">
        OBS のゲーム映像をプレビューするため、利用環境によって仮想カメラへの許可が必要です。
      </p>
      <p class="message">
        {#if clientPlatform === 'macos'}
          macOS デスクトップ版では「システム設定」→「プライバシーとセキュリティ」→「カメラ」で Splat
          Replay を許可し、内蔵 WebView から確認が出た場合も許可してください。
        {/if}
        localhost をブラウザで開いている場合は、そのブラウザのサイト設定でカメラを許可してください。
      </p>
      <p class="message">
        LAN
        で別端末から閲覧する場合、カメラ許可は不要で、この案内は通常表示されません。この案内が表示される端末で許可を拒否し、映像が表示されない場合は、該当する設定で許可を確認してから画面を再読み込みしてください。
      </p>
    </div>

    <div class="checkbox-container">
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={dontShowAgain} />
        <span>再度表示しない</span>
      </label>
    </div>
  </div>
</BaseDialog>

<style>
  .dialog-content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .info-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    text-align: left;
  }

  .message {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.95rem;
    line-height: 1.6;
    text-align: left;
  }

  .checkbox-container {
    padding: 0.5rem 0;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 0.9rem;
    user-select: none;
  }

  .checkbox-label input[type='checkbox'] {
    width: 1.1rem;
    height: 1.1rem;
    cursor: pointer;
    accent-color: var(--accent-color);
  }
</style>
