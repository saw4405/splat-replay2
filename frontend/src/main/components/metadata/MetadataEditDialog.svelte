<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import MetadataForm from './MetadataForm.svelte';
  import { getMetadataOptions } from '../../api/metadata';
  import type { MetadataOptionItem } from '../../api/types';
  import {
    cloneEditableMetadata,
    createEmptyEditableMetadata,
    type EditableMetadata,
  } from '../../metadata/editable';

  const dispatch = createEventDispatcher();

  export let visible: boolean = false;
  export let videoId: string = '';
  export let metadata: EditableMetadata;

  let editedMetadata: EditableMetadata = createEmptyEditableMetadata();
  let matchOptions: MetadataOptionItem[] = [];
  let ruleOptions: MetadataOptionItem[] = [];
  let stageOptions: MetadataOptionItem[] = [];
  let judgementOptions: MetadataOptionItem[] = [];

  let previousVisible = false;

  $: if (visible && !previousVisible && metadata) {
    editedMetadata = cloneEditableMetadata(metadata);
    previousVisible = true;
  } else if (!visible) {
    previousVisible = false;
  }

  async function loadMetadataOptions(): Promise<void> {
    try {
      const options = await getMetadataOptions();
      matchOptions = options.matches;
      ruleOptions = options.rules;
      stageOptions = options.stages;
      judgementOptions = options.judgements;
    } catch (error) {
      console.error('Failed to load metadata options:', error);
    }
  }

  onMount(() => {
    void loadMetadataOptions();
  });

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
  <div class="metadata-form-scroll">
    <MetadataForm
      bind:metadata={editedMetadata}
      {matchOptions}
      {ruleOptions}
      {stageOptions}
      {judgementOptions}
    />
  </div>
</BaseDialog>

<style>
  .metadata-form-scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    padding-right: 0.25rem;
  }
</style>
