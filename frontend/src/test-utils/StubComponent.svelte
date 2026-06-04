<script lang="ts">
  interface Props {
    isLoading?: boolean;
    videos?: unknown[];
    battles?: unknown[];
  }

  let { isLoading = false, videos = [], battles = [] }: Props = $props();
</script>

<div
  data-testid="stub-component"
  data-is-loading={String(isLoading)}
  data-videos-length={String(videos.length)}
  data-battles-length={String(battles.length)}
></div>
