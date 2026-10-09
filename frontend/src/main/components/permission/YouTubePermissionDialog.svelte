<script lang="ts">
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import { getSetupPlatform } from '../../../setup/platform';

  interface Props {
    open?: boolean;
    onClose?: () => void;
  }

  let { open = $bindable(false), onClose }: Props = $props();

  const setupPlatform = getSetupPlatform();
  let dontShowAgain = $state(false);

  async function handleClose(): Promise<void> {
    if (dontShowAgain) {
      try {
        await fetch('/api/settings/youtube-permission-dialog', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shown: true }),
        });
      } catch (error) {
        console.error('Failed to save youtube permission dialog state:', error);
      }
    }
    open = false;
    onClose?.();
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
    <h2 id="dialog-title">YouTubeへのアクセス許可</h2>
  {/snippet}

  <div class="dialog-content">
    <div class="info-section">
      <p class="message">
        Googleの認証画面が表示された場合、Googleアカウントでログインし、YouTubeへのアクセスを許可してください。
      </p>
      <p class="message">
        このアプリは、編集した動画をYouTubeに自動アップロードするために、YouTubeへのアクセス権限を使用します。
      </p>
      {#if setupPlatform === 'macos'}
        <p class="message">
          macOSのKeychainアクセス確認が別に表示された場合は、内容を確認して許可してください。これはGoogleの認証画面とは別の確認です。
        </p>
      {/if}
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
