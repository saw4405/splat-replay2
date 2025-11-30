<script lang="ts">
  import BaseDialog from "./BaseDialog.svelte";

  export let isOpen = false;
  export let message = "";

  function handleClose(): void {
    isOpen = false;
    dispatchEvent(new CustomEvent("close"));
  }
</script>

<BaseDialog
  bind:open={isOpen}
  title="メッセージ"
  footerVariant="compact"
  primaryButtonText="閉じる"
  on:primary-click={handleClose}
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
