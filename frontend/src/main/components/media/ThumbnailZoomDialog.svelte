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
    flex: 1 1 auto;
    align-items: center;
    justify-content: center;
    min-height: 0;
    overflow: hidden;
  }

  .thumbnail-image {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: contain;
    border-radius: 8px;
  }
</style>
