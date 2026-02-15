<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';

  const dispatch = createEventDispatcher();

  export let open = false;
  export let title = '';
  export let showHeader = true;
  export let showFooter = true;
  export let footerVariant: 'simple' | 'compact' | 'custom' = 'simple';
  export let primaryButtonText = '保存';
  export let secondaryButtonText = 'キャンセル';
  export let maxWidth = '60rem';
  export let maxHeight = '90vh';
  export let minHeight: string | undefined = undefined;
  export let disablePrimaryButton = false;
  export let disableSecondaryButton = false;
  export let allowBackdropClose = false; // ダイアログ外クリックで閉じるかどうか
  export let showCloseButton = false; // ×ボタンを表示するかどうか

  const handleKeydown = (event: KeyboardEvent): void => {
    if (event.key === 'Escape' && allowBackdropClose) {
      closeDialog();
    }
  };

  $: resolvedMinHeight = minHeight ?? `clamp(37.5rem, 80vh, ${maxHeight})`;

  $: {
    if (open) {
      window.addEventListener('keydown', handleKeydown);
    } else {
      window.removeEventListener('keydown', handleKeydown);
    }
  }

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });

  function closeDialog(): void {
    open = false;
  }

  function handlePrimaryClick(): void {
    dispatch('primary-click', {});
  }

  function handleSecondaryClick(): void {
    dispatch('secondary-click', {});
    closeDialog();
  }
</script>

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
  <div
    class="dialog-overlay"
    role="presentation"
    on:click={allowBackdropClose ? closeDialog : undefined}
  >
    <div
      class="dialog-container"
      role="dialog"
      aria-modal="true"
      aria-labelledby={showHeader ? 'dialog-title' : undefined}
      on:click|stopPropagation
      style:max-width={maxWidth}
      style:max-height={maxHeight}
      style:min-height={resolvedMinHeight}
    >
      {#if showHeader}
        <header class="dialog-header">
          <slot name="header">
            <h2 id="dialog-title">{title}</h2>
          </slot>
          {#if showCloseButton}
            <button class="icon-button" type="button" aria-label="閉じる" on:click={closeDialog}>
              ✕
            </button>
          {/if}
        </header>
      {/if}

      <section class="dialog-body">
        <slot />
      </section>

      {#if showFooter}
        <footer class="dialog-footer">
          <slot name="footer-status" />

          {#if footerVariant === 'simple'}
            <div class="actions">
              <button
                type="button"
                class="action-button secondary"
                on:click={handleSecondaryClick}
                disabled={disableSecondaryButton}
              >
                <span aria-hidden="true" class="button-background"></span>
                <span class="button-content">{secondaryButtonText}</span>
              </button>
              <button
                type="button"
                class="action-button primary"
                on:click={handlePrimaryClick}
                disabled={disablePrimaryButton}
              >
                <span aria-hidden="true" class="button-background"></span>
                <span class="button-content">{primaryButtonText}</span>
              </button>
            </div>
          {:else if footerVariant === 'compact'}
            <div class="actions">
              <button
                type="button"
                class="action-button primary"
                on:click={handlePrimaryClick}
                disabled={disablePrimaryButton}
              >
                <span aria-hidden="true" class="button-background"></span>
                <span class="button-content">{primaryButtonText}</span>
              </button>
            </div>
          {:else}
            <slot name="footer" />
          {/if}
        </footer>
      {/if}
    </div>
  </div>
{/if}

<style>
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-surface-deep), 0.85) 0%,
      rgba(var(--theme-rgb-surface-overlay), 0.9) 100%
    );
    backdrop-filter: blur(16px) saturate(180%);
    -webkit-backdrop-filter: blur(16px) saturate(180%);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 2rem;
    animation: overlay-fade-in 0.3s ease;
  }

  @keyframes overlay-fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .dialog-container {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.08) 0%,
      rgba(var(--theme-rgb-white), 0.04) 100%
    );
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border: 1px solid rgba(var(--theme-rgb-accent), 0.2);
    border-radius: 1.25rem;
    width: min(var(--max-width, 60rem), 100%);
    display: flex;
    flex-direction: column;
    box-shadow:
      0 1.5rem 4rem rgba(var(--theme-rgb-black), 0.6),
      0 0 0 1px rgba(var(--theme-rgb-white), 0.05) inset,
      0 0 5rem rgba(var(--theme-rgb-accent), 0.15);
    animation: dialog-scale-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  @keyframes dialog-scale-in {
    from {
      opacity: 0;
      transform: scale(0.95) translateY(1.25rem);
    }
    to {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.5rem 2rem 1.25rem;
    border-bottom: 1px solid rgba(var(--theme-rgb-white), 0.1);
    background: linear-gradient(to bottom, rgba(var(--theme-rgb-white), 0.05) 0%, transparent 100%);
    flex-shrink: 0;
  }

  .dialog-header :global(h2) {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--accent-color);
    text-shadow:
      0 0 1.25rem rgba(var(--theme-rgb-accent), 0.3),
      0 0.125rem 0.25rem rgba(var(--theme-rgb-black), 0.5);
  }

  .icon-button {
    border: none !important;
    background: none !important;
    background-color: transparent !important;
    padding: 0;
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(var(--theme-rgb-white), 0.6);
    font-size: 1.2rem;
    cursor: pointer;
    transition: color 0.2s ease;
    box-shadow: none !important;
    appearance: none;
    flex-shrink: 0;
  }

  .icon-button:hover,
  .icon-button:focus-visible,
  .icon-button:active {
    background: none !important;
    background-color: transparent !important;
    box-shadow: none !important;
    outline: none;
    color: var(--theme-status-danger-soft);
  }

  .icon-button:focus-visible {
    outline: 0.125rem solid rgba(var(--theme-rgb-danger-soft-alt), 0.7);
    outline-offset: 0.125rem;
  }

  .dialog-body {
    padding: 2rem;
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }

  .dialog-footer {
    background: linear-gradient(180deg, rgba(var(--theme-rgb-white), 0.02) 0%, transparent 100%);
    border-top: 1px solid rgba(var(--theme-rgb-white), 0.1);
    padding: 1.5rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    flex-shrink: 0;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    align-items: center;
  }

  .action-button {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    border-radius: 0.75rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.15);
    background: transparent;
    color: rgba(var(--theme-rgb-white), 0.75);
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    padding: 0;
    min-width: 6.25rem;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }

  .action-button .button-background {
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.16) 0%,
      rgba(var(--theme-rgb-white), 0.05) 100%
    );
    opacity: 0.2;
    transition: opacity 0.3s ease;
  }

  .action-button .button-content {
    position: relative;
    z-index: 1;
    padding: 0.75rem 1.6rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: color 0.3s ease;
  }

  .action-button:hover {
    transform: translateY(-0.125rem);
  }

  .action-button:active {
    transform: translateY(0);
  }

  .action-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
  }

  .action-button.primary {
    border-color: rgba(var(--theme-rgb-accent), 0.35);
    color: var(--accent-color);
  }

  .action-button.primary .button-background {
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-color-strong) 100%);
    opacity: 0.18;
  }

  .action-button.primary:hover {
    box-shadow:
      0 0.25rem 1.25rem rgba(var(--theme-rgb-accent), 0.3),
      0 0 2.5rem rgba(var(--theme-rgb-accent), 0.2),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.1);
  }

  .action-button.primary:hover .button-background {
    opacity: 1;
  }

  .action-button.primary:hover .button-content {
    color: var(--theme-color-black);
  }

  .action-button.secondary {
    border-color: rgba(var(--theme-rgb-white), 0.12);
    color: rgba(var(--theme-rgb-white), 0.88);
  }

  .action-button.secondary .button-background {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.15) 0%,
      rgba(var(--theme-rgb-white), 0.04) 100%
    );
    opacity: 0.12;
  }

  .action-button.secondary:hover {
    box-shadow:
      0 0.375rem 1.125rem rgba(var(--theme-rgb-black), 0.25),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.08);
    border-color: rgba(var(--theme-rgb-white), 0.2);
  }

  .action-button.secondary:hover .button-background {
    opacity: 0.4;
  }

  .action-button:disabled .button-background {
    opacity: 0.08;
  }

  .action-button:disabled:hover {
    box-shadow: none;
  }

  .action-button:focus-visible {
    outline: 0.125rem solid rgba(var(--theme-rgb-accent), 0.55);
    outline-offset: 0.1875rem;
  }

  @media (max-width: 56.25rem) {
    .dialog-container {
      height: clamp(25rem, 90vh, var(--max-height, 90vh));
    }

    .dialog-header {
      padding: 1.25rem 1.5rem 1rem;
    }

    .dialog-header :global(h2) {
      font-size: 1.5rem;
    }

    .dialog-body {
      padding: 1.5rem;
    }

    .dialog-footer {
      padding: 1rem 1.5rem;
    }

    .actions {
      flex-direction: column-reverse;
    }

    .action-button {
      width: 100%;
    }
  }
</style>
