<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import BaseDialog from './BaseDialog.svelte';

  const dispatch = createEventDispatcher();

  export let isOpen = false;
  export let message = '';
  export let confirmText = 'OK';
  export let cancelText = 'キャンセル';

  function handleConfirm(): void {
    dispatch('confirm');
    isOpen = false;
  }

  function handleCancel(): void {
    dispatch('cancel');
    isOpen = false;
  }
</script>

<BaseDialog
  bind:open={isOpen}
  title="確認"
  footerVariant="simple"
  primaryButtonText={confirmText}
  secondaryButtonText={cancelText}
  on:primary-click={handleConfirm}
  on:secondary-click={handleCancel}
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
