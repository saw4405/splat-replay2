<script lang="ts">
  import BaseDialog from './BaseDialog.svelte';

  interface Props {
    isOpen?: boolean;
    message?: string;
    confirmText?: string;
    cancelText?: string;
    onConfirm?: () => void;
    onCancel?: () => void;
  }

  let {
    isOpen = $bindable(false),
    message = '',
    confirmText = 'OK',
    cancelText = 'キャンセル',
    onConfirm,
    onCancel,
  }: Props = $props();

  function handleConfirm(): void {
    isOpen = false;
    onConfirm?.();
  }

  function handleCancel(): void {
    onCancel?.();
  }
</script>

<BaseDialog
  bind:open={isOpen}
  title="確認"
  footerVariant="simple"
  primaryButtonText={confirmText}
  secondaryButtonText={cancelText}
  onPrimaryClick={handleConfirm}
  onSecondaryClick={handleCancel}
  maxWidth="28rem"
  minHeight="auto"
>
  <p class="message">{message}</p>
</BaseDialog>

<style>
  .message {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: rgba(var(--theme-rgb-white), 0.9);
    word-break: break-word;
    white-space: pre-line;
    text-align: left;
  }
</style>
