<script lang="ts">
  interface Props {
    open?: boolean;
  }

  let { open = false }: Props = $props();
</script>

<div data-testid="open-stub" data-open={open}></div>
