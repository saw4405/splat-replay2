<script lang="ts">
  import { AlertTriangle, X } from "lucide-svelte";

  export let open = false;
  export let title = "確認";
  export let message = "";
  export let confirmText = "確認";
  export let cancelText = "キャンセル";
  export let onConfirm: (() => void) | undefined = undefined;
  export let onCancel: (() => void) | undefined = undefined;
  export let variant: "warning" | "info" = "info";

  function handleConfirm(): void {
    if (onConfirm) {
      onConfirm();
    }
    open = false;
  }

  function handleCancel(): void {
    if (onCancel) {
      onCancel();
    }
    open = false;
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      handleCancel();
    }
  }
</script>

{#if open}
  <div class="dialog-backdrop" on:click={handleBackdropClick} role="presentation">
    <div class="dialog glass-surface" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div class="dialog-header">
        {#if variant === "warning"}
          <div class="header-icon">
            <AlertTriangle class="icon warning-icon" size={24} />
          </div>
        {/if}
        <h2 id="confirm-title" class="dialog-title">{title}</h2>
        <button
          class="close-button"
          type="button"
          aria-label="閉じる"
          on:click={handleCancel}
        >
          <X class="icon" size={20} />
        </button>
      </div>

      <div class="dialog-content">
        <p class="message">{message}</p>
      </div>

      <div class="dialog-actions">
        <button
          class="button button-primary"
          type="button"
          on:click={handleConfirm}
        >
          {confirmText}
        </button>
        <button
          class="button button-secondary"
          type="button"
          on:click={handleCancel}
        >
          {cancelText}
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
    max-width: 450px;
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

  .warning-icon {
    color: #ffa500;
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
    padding: 1.5rem;
  }

  .message {
    margin: 0;
    font-size: 1rem;
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

  .icon {
    display: block;
  }
</style>
