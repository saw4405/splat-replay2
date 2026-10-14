<script lang="ts">
  import BaseDialog from '../../../common/components/BaseDialog.svelte';

  interface Props {
    visible?: boolean;
    videoUrl?: string;
    videoTitle?: string;
  }

  let { visible = $bindable(false), videoUrl = '', videoTitle = '' }: Props = $props();

  let loadState = $state<'loading' | 'ready' | 'error'>('loading');
  let videoElement: HTMLVideoElement | undefined;

  $effect(() => {
    if (visible && videoUrl) loadState = 'loading';
  });

  function retryPlayback(): void {
    loadState = 'loading';
    videoElement?.load();
  }
</script>

<BaseDialog
  bind:open={visible}
  title={videoTitle}
  showFooter={false}
  maxWidth="90vw"
  maxHeight="90vh"
  showCloseButton={true}
>
  <div class="video-container">
    <video
      bind:this={videoElement}
      controls
      autoplay
      class="video-player"
      src={videoUrl}
      aria-label={`${videoTitle}を再生`}
      onloadstart={() => (loadState = 'loading')}
      oncanplay={() => (loadState = 'ready')}
      onerror={() => (loadState = 'error')}
    >
      <track kind="captions" />
      お使いのブラウザは動画再生に対応していません。
    </video>
    {#if loadState === 'loading'}
      <p class="video-status" role="status">動画を準備しています...</p>
    {:else if loadState === 'error'}
      <div class="video-status video-error" role="alert">
        <span>動画を読み込めませんでした。</span>
        <button class="action-button primary" type="button" onclick={retryPlayback}>
          <span aria-hidden="true" class="button-background"></span>
          <span class="button-content">再試行</span>
        </button>
      </div>
    {/if}
  </div>
</BaseDialog>

<style>
  .video-container {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    overflow: auto;
    flex-direction: column;
  }

  .video-status {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    margin: 0.75rem 0 0;
  }

  .video-error {
    color: var(--theme-status-danger-soft);
  }

  .video-player {
    width: 100%;
    height: auto;
    max-height: 100%;
    display: block;
  }
</style>
