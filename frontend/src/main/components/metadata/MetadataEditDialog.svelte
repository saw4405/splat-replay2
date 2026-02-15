<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import MetadataForm from './MetadataForm.svelte';
  import { getMetadataOptions } from '../../api/metadata';
  import type { MetadataOptionItem } from '../../api/types';

  type WeaponSlots = [string, string, string, string];

  interface EditableMetadata {
    match: string;
    rule: string;
    stage: string;
    rate: string;
    judgement: string;
    kill: number;
    death: number;
    special: number;
    allies: WeaponSlots;
    enemies: WeaponSlots;
  }

  const dispatch = createEventDispatcher();

  export let visible: boolean = false;
  export let videoId: string = '';
  export let metadata: EditableMetadata;

  function normaliseWeaponSlots(values: string[] | undefined): WeaponSlots {
    const normalised = values?.slice(0, 4) ?? [];
    while (normalised.length < 4) {
      normalised.push('');
    }
    return [normalised[0] ?? '', normalised[1] ?? '', normalised[2] ?? '', normalised[3] ?? ''];
  }

  function createEditableMetadata(value: EditableMetadata): EditableMetadata {
    return {
      ...value,
      allies: normaliseWeaponSlots(value.allies),
      enemies: normaliseWeaponSlots(value.enemies),
    };
  }

  let editedMetadata: EditableMetadata = {
    match: '',
    rule: '',
    stage: '',
    rate: '',
    judgement: '',
    kill: 0,
    death: 0,
    special: 0,
    allies: ['', '', '', ''],
    enemies: ['', '', '', ''],
  };
  let matchOptions: MetadataOptionItem[] = [];
  let ruleOptions: MetadataOptionItem[] = [];
  let stageOptions: MetadataOptionItem[] = [];
  let judgementOptions: MetadataOptionItem[] = [];

  let previousVisible = false;

  $: if (visible && !previousVisible && metadata) {
    editedMetadata = createEditableMetadata(metadata);
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
