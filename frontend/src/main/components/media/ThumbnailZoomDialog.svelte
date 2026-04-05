<script lang="ts">
  import BaseDialog from '../../../common/components/BaseDialog.svelte';

  interface Props {
    visible?: boolean;
    imageUrl?: string;
    imageTitle?: string;
  }

  let { visible = $bindable(false), imageUrl = '', imageTitle = '' }: Props = $props();
</script>

<BaseDialog
  bind:open={visible}
  title={imageTitle}
  showFooter={false}
  maxWidth="90vw"
  maxHeight="90vh"
  showCloseButton={true}
>
  <div class="image-container">
    <img src={imageUrl} alt={imageTitle} class="thumbnail-image" />
  </div>
</BaseDialog>

<style>
  .image-container {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    overflow: auto;
  }

  .thumbnail-image {
    max-width: 100%;
    max-height: 100%;
    display: block;
    border-radius: 8px;
  }
</style>
