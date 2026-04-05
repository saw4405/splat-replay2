<script lang="ts">
  import { Info, CircleCheck, TriangleAlert, CircleAlert } from 'lucide-svelte';
  import BaseDialog from './BaseDialog.svelte';

  interface Props {
    isOpen?: boolean;
    message?: string;
    variant?: 'info' | 'success' | 'warning' | 'error';
    title?: string;
    buttonText?: string;
    onClose?: () => void;
  }

  let {
    isOpen = $bindable(false),
    message = '',
    variant = 'info',
    title = '',
    buttonText = '閉じる',
    onClose,
  }: Props = $props();

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

  const resolvedTitle = $derived(title || variantConfig[variant].title);
  const IconComponent = $derived(variantConfig[variant].icon);

  function handleClose(): void {
    isOpen = false;
    onClose?.();
  }
</script>

<BaseDialog
  bind:open={isOpen}
  footerVariant="compact"
  primaryButtonText={buttonText}
  onPrimaryClick={handleClose}
  maxWidth="28rem"
  minHeight="auto"
>
  {#snippet header()}
    <div class="notification-header">
      <div class="notification-icon" style="color: {variantConfig[variant].color};">
        <IconComponent size={28} />
      </div>
      <h2 id="dialog-title" class="notification-title">{resolvedTitle}</h2>
    </div>
  {/snippet}

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
