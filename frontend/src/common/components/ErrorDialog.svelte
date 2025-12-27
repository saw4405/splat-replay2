<script lang="ts">
  import { AlertCircle } from 'lucide-svelte';
  import BaseDialog from './BaseDialog.svelte';
  import type { ApiError } from '../types';

  export let open = false;
  export let error: ApiError | null = null;
  export let title = 'エラーが発生しました';
  export let message = '';
  export let onClose: (() => void) | undefined = undefined;
  export let onRetry: (() => void) | undefined = undefined;

  function handleClose(): void {
    open = false;
    if (onClose) {
      onClose();
    }
  }

  function handleRetry(): void {
    if (onRetry) {
      onRetry();
    }
    handleClose();
  }

  function handleSecondaryClick(): void {
    handleClose();
  }
</script>

<BaseDialog
  bind:open
  {title}
  showHeader={false}
  footerVariant={onRetry ? 'simple' : 'compact'}
  primaryButtonText={onRetry ? '再試行' : '閉じる'}
  secondaryButtonText="閉じる"
  on:primary-click={onRetry ? handleRetry : handleClose}
  on:secondary-click={handleSecondaryClick}
  maxWidth="32rem"
  minHeight="auto"
>
  <div class="error-dialog-content">
    <div class="error-header">
      <div class="error-icon">
        <AlertCircle size={48} />
      </div>
      <h2 class="error-title">{title}</h2>
    </div>

    <div class="error-body">
      <p class="error-message">{message || (error ? error.error : '')}</p>

      {#if error}
        {#if error.error_code}
          <p class="error-code">エラーコード: {error.error_code}</p>
        {/if}

        {#if error.recovery_action}
          <div class="recovery-section">
            <h3 class="recovery-title">推奨される対処方法</h3>
            <p class="recovery-action">{error.recovery_action}</p>
          </div>
        {/if}
      {/if}
    </div>
  </div>
</BaseDialog>

<style>
  .error-dialog-content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .error-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .error-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(244, 67, 54, 0.2), rgba(211, 47, 47, 0.3));
    color: #f44336;
  }

  .error-title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
    text-align: center;
  }

  .error-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .error-message {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.9);
    text-align: left;
  }

  .error-code {
    margin: 0;
    padding: 0.5rem 0.75rem;
    background: rgba(244, 67, 54, 0.1);
    border-left: 3px solid #f44336;
    border-radius: 4px;
    font-size: 0.875rem;
    font-family: 'Courier New', monospace;
    color: rgba(255, 255, 255, 0.8);
  }

  .recovery-section {
    padding: 1rem;
    background: rgba(33, 150, 243, 0.1);
    border-left: 3px solid #2196f3;
    border-radius: 4px;
  }

  .recovery-title {
    margin: 0 0 0.5rem 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: #2196f3;
  }

  .recovery-action {
    margin: 0;
    font-size: 0.875rem;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.85);
  }
</style>
