<script lang="ts">
  interface Props {
    isOpen?: boolean;
  }

  let { isOpen = $bindable(false) }: Props = $props();
</script>

<div data-testid="progress-dialog-stub" data-is-open={String(isOpen)}></div>
