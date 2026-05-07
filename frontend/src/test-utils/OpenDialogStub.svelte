<script lang="ts">
  interface Props {
    open?: boolean;
  }

  let { open = $bindable(false) }: Props = $props();
</script>

<div data-testid="youtube-dialog-stub" data-open={String(open)}></div>
