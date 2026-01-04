<script lang="ts">
  import BaseDialog from '../../../common/components/BaseDialog.svelte';

  export let visible: boolean = false;
  export let videoUrl: string = '';
  export let videoTitle: string = '';
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
    <video controls autoplay class="video-player">
      <source src={videoUrl} type="video/mp4" />
      <track kind="captions" />
      お使いのブラウザは動画再生に対応していません。
    </video>
  </div>
</BaseDialog>

<style>
  .video-container {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    overflow: auto;
  }

  .video-player {
    width: 100%;
    height: auto;
    max-height: 100%;
    display: block;
  }
</style>
