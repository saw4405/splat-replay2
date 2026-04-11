<script lang="ts">
  interface Props {
    visible?: boolean;
  }

  let { visible = false }: Props = $props();
</script>

<div data-testid="visible-stub" data-visible={visible}></div>
