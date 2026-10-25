<script lang="ts">
  import ImportedVideoDialog from './ImportedVideoDialog.svelte';

  let dialogOpen = $state(false);
  let fileInput: HTMLInputElement | undefined;
  let pendingFile = $state<File | null>(null);

  function chooseFile(): void {
    fileInput?.click();
  }

  function isFileDrag(event: DragEvent): boolean {
    return Boolean(event.dataTransfer?.types.includes('Files'));
  }

  function handleDragOver(event: DragEvent): void {
    if (!isFileDrag(event)) return;
    event.preventDefault();
  }

  function handleDrop(event: DragEvent): void {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    const file = event.dataTransfer?.files.item(0);
    if (!file) return;
    dialogOpen = true;
    pendingFile = file;
  }

  function handleFileChange(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.item(0);
    input.value = '';
    if (!file) return;
    dialogOpen = true;
    pendingFile = file;
  }
</script>

<svelte:window ondragover={handleDragOver} ondrop={handleDrop} />

<input
  bind:this={fileInput}
  class="file-input"
  type="file"
  accept="video/*,.mkv,.mov,.mp4,.m4v,.avi,.webm"
  aria-label="編集する動画を選択"
  onchange={handleFileChange}
/>
<ImportedVideoDialog bind:open={dialogOpen} file={pendingFile} onChooseFile={chooseFile} />

<style>
  .file-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>
