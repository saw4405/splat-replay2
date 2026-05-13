<script lang="ts">
  interface Props {
    isOpen?: boolean;
    variant?: string;
    message?: string;
    onClose?: () => void;
  }

  let { isOpen = false, variant = 'info', message = '', onClose }: Props = $props();
</script>

{#if isOpen}
  <div data-testid="notification-dialog-stub" data-variant={variant} role="dialog">
    <span>{message}</span>
    <button type="button" data-testid="notification-dialog-close" onclick={() => onClose?.()}>
      close
    </button>
  </div>
{/if}
