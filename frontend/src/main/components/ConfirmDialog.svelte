<script lang="ts">
  import BaseDialog from "./BaseDialog.svelte";

  export let isOpen = false;
  export let message = "";
  export let confirmText = "OK";
  export let cancelText = "キャンセル";

  function handleConfirm(): void {
    isOpen = false;
    dispatchEvent(new CustomEvent("confirm"));
  }

  function handleCancel(): void {
    isOpen = false;
    dispatchEvent(new CustomEvent("cancel"));
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
    color: rgba(255, 255, 255, 0.9);
    word-break: break-word;
    white-space: pre-line;
    text-align: left;
  }
</style>
