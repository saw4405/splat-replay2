<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import BaseDialog from './BaseDialog.svelte';
  import MetadataForm from './MetadataForm.svelte';

  const dispatch = createEventDispatcher();

  export let visible: boolean = false;
  export let videoId: string = '';
  export let metadata: {
    match: string;
    rule: string;
    stage: string;
    rate: string;
    judgement: string;
    kill: number;
    death: number;
    special: number;
  };

  let editedMetadata = {
    match: '',
    rule: '',
    stage: '',
    rate: '',
    judgement: '',
    kill: 0,
    death: 0,
    special: 0,
  };

  let previousVisible = false;

  $: if (visible && !previousVisible && metadata) {
    editedMetadata = { ...metadata };
    previousVisible = true;
  } else if (!visible) {
    previousVisible = false;
  }

  function handleSave(): void {
    dispatch('save', { videoId, metadata: editedMetadata });
    visible = false;
  }

  function handleCancel(): void {
    visible = false;
  }
</script>

<BaseDialog
  bind:open={visible}
  title="メタデータ編集"
  footerVariant="simple"
  primaryButtonText="保存"
  secondaryButtonText="キャンセル"
  on:primary-click={handleSave}
  on:secondary-click={handleCancel}
  maxWidth="37.5rem"
  maxHeight="85vh"
>
  <MetadataForm bind:metadata={editedMetadata} />
</BaseDialog>
