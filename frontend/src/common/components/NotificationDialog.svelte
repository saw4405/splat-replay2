<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Info, CircleCheck, TriangleAlert, CircleAlert } from 'lucide-svelte';
  import BaseDialog from './BaseDialog.svelte';

  export let isOpen = false;
  export let message = '';
  export let variant: 'info' | 'success' | 'warning' | 'error' = 'info';
  export let title = '';
  export let buttonText = '閉じる';

  const dispatch = createEventDispatcher();

  $: resolvedTitle = title || variantConfig[variant].title;
  $: IconComponent = variantConfig[variant].icon;

  const variantConfig = {
    info: {
      title: 'メッセージ',
      icon: Info,
      color: 'var(--theme-status-info)',
      gradient:
        'linear-gradient(135deg, rgba(var(--theme-rgb-info), 0.2), rgba(var(--theme-rgb-info-strong), 0.3))',
    },
    success: {
      title: '完了',
      icon: CircleCheck,
      color: 'var(--theme-status-success)',
      gradient:
        'linear-gradient(135deg, rgba(var(--theme-rgb-success), 0.2), rgba(var(--theme-rgb-success-strong), 0.3))',
    },
    warning: {
      title: '警告',
      icon: TriangleAlert,
      color: 'var(--theme-status-warning)',
      gradient:
        'linear-gradient(135deg, rgba(var(--theme-rgb-warning), 0.2), rgba(var(--theme-rgb-warning-strong), 0.3))',
    },
    error: {
      title: 'エラー',
      icon: CircleAlert,
      color: 'var(--theme-status-danger)',
      gradient:
        'linear-gradient(135deg, rgba(var(--theme-rgb-danger), 0.2), rgba(var(--theme-rgb-danger-strong), 0.3))',
    },
  };

  function handleClose(): void {
    isOpen = false;
    dispatch('close');
  }
</script>

<BaseDialog
  bind:open={isOpen}
  footerVariant="compact"
  primaryButtonText={buttonText}
  on:primary-click={handleClose}
  maxWidth="28rem"
  minHeight="auto"
>
  <svelte:fragment slot="header">
    <div class="notification-header">
      <div class="notification-icon" style="color: {variantConfig[variant].color};">
        <svelte:component this={IconComponent} size={28} />
      </div>
      <h2 id="dialog-title" class="notification-title">{resolvedTitle}</h2>
    </div>
  </svelte:fragment>

  <p class="message">{message}</p>
</BaseDialog>

<style>
  .notification-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex: 1;
  }

  .notification-icon {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .notification-title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: rgba(var(--theme-rgb-white), 0.95);
  }

  .message {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: rgba(var(--theme-rgb-white), 0.9);
    word-break: break-word;
    white-space: pre-line;
    text-align: center;
    width: 100%;
  }
</style>
