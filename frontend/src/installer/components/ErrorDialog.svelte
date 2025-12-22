<script lang="ts">
  import { AlertCircle, X } from 'lucide-svelte';
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

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }
</script>

{#if open && (error || message)}
  <div class="dialog-backdrop" on:click={handleBackdropClick} role="presentation">
    <div class="dialog glass-surface" role="dialog" aria-modal="true" aria-labelledby="error-title">
      <div class="dialog-header">
        <div class="header-icon">
          <AlertCircle class="icon error-icon" size={24} />
        </div>
        <h2 id="error-title" class="dialog-title">{title}</h2>
        <button class="close-button" type="button" aria-label="閉じる" on:click={handleClose}>
          <X class="icon" size={20} />
        </button>
      </div>

      <div class="dialog-content">
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

      <div class="dialog-actions">
        {#if onRetry}
          <button class="button button-primary" type="button" on:click={handleRetry}>
            再試行
          </button>
        {/if}
        <button class="button button-secondary" type="button" on:click={handleClose}>
          閉じる
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fade-in 0.2s ease-out;
  }

  @keyframes fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .dialog {
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    animation: slide-up 0.3s ease-out;
  }

  @keyframes slide-up {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .dialog-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.5rem;
    border-bottom: 1px solid var(--divider-color);
  }

  .header-icon {
    flex-shrink: 0;
  }

  .dialog-title {
    flex: 1;
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .close-button {
    flex-shrink: 0;
    width: 2rem;
    height: 2rem;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .close-button:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-primary);
    transform: none;
    box-shadow: none;
  }

  .dialog-content {
    flex: 1;
    padding: 1.5rem;
    overflow-y: auto;
  }

  .error-message {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-primary);
  }

  .error-code {
    margin: 0 0 1.5rem 0;
    font-size: 0.875rem;
    font-family: monospace;
    color: var(--text-secondary);
    padding: 0.5rem;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
  }

  .recovery-section {
    margin-top: 1.5rem;
    padding: 1rem;
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
    border-radius: 8px;
  }

  .recovery-title {
    margin: 0 0 0.5rem 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--accent-color);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .recovery-action {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.6;
    color: var(--text-primary);
  }

  .dialog-actions {
    display: flex;
    gap: 0.75rem;
    padding: 1.5rem;
    border-top: 1px solid var(--divider-color);
    justify-content: flex-end;
  }

  .button {
    padding: 0.625rem 1.5rem;
    font-size: 0.9375rem;
    font-weight: 500;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
  }

  .button-primary {
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    color: white;
    border-color: var(--accent-color);
  }

  .button-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px var(--accent-glow);
  }

  .button-secondary {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .button-secondary:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }
</style>
