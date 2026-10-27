<script lang="ts">
  import { Move, Upload, RotateCcw } from 'lucide-svelte';
  import type { ThumbnailAsset, ThumbnailDesign } from '../../api/thumbnailDesign';
  let {
    background,
    images,
    moving,
    onmove,
    onupload,
  }: {
    background: ThumbnailDesign['background'];
    images: ThumbnailAsset[];
    moving: boolean;
    onmove: () => void;
    onupload: (file: File | undefined) => void;
  } = $props();
  let input = $state<HTMLInputElement>();
</script>

<section class="background-panel" aria-label="背景の設定">
  <div class="source-row">
    <h3>背景</h3>
    <select aria-label="背景" bind:value={background.source}
      ><option value="result">リザルト画面</option><option value="image">画像ファイル</option
      ></select
    >
    {#if background.source === 'image'}<select
        class="image-choice"
        aria-label="背景画像"
        bind:value={background.asset}
        ><option value="">画像を選択</option>{#each images as a}<option value={a.id}
            >{a.name}</option
          >{/each}</select
      >{/if}
    <button type="button" class="upload" onclick={() => input?.click()}
      ><Upload size={14} />アップロード</button
    >
    <input
      class="file-input"
      bind:this={input}
      type="file"
      accept="image/png,image/jpeg,image/webp"
      aria-label="背景画像をアップロード"
      onchange={(event) => {
        onupload(event.currentTarget.files?.[0]);
        event.currentTarget.value = '';
      }}
    />
  </div>
  <div class="transform-row">
    <button
      type="button"
      class="move"
      class:active={moving}
      aria-label="背景をドラッグで移動"
      aria-pressed={moving}
      onclick={onmove}><Move size={15} />{moving ? '移動を終了' : '背景を移動'}</button
    >
    <div class="position">
      <label
        >横位置<input
          aria-label="背景のX"
          type="number"
          bind:value={background.x}
          min="-7680"
          max="7680"
        /></label
      ><label
        >縦位置<input
          aria-label="背景のY"
          type="number"
          bind:value={background.y}
          min="-4320"
          max="4320"
        /></label
      >
    </div>
    <div class="scale">
      <label for="thumbnail-background-scale"
        >背景の倍率<output>{Math.round(background.scale * 100)}%</output></label
      ><input
        id="thumbnail-background-scale"
        aria-label="背景の倍率"
        title="100%で画面全体にフィット"
        type="range"
        min="1"
        max="4"
        step="0.01"
        bind:value={background.scale}
      />
    </div>
    <button
      class="reset"
      type="button"
      aria-label="背景の位置・倍率を戻す"
      title="背景の位置を中央・倍率を100%に戻す"
      onclick={() => {
        background.x = 0;
        background.y = 0;
        background.scale = 1;
      }}><RotateCcw size={15} /></button
    >
  </div>
</section>

<style>
  .background-panel {
    border-top: 1px solid var(--glass-border);
    padding: 0.75rem 0 0.85rem;
    flex-shrink: 0;
  }
  h3 {
    margin: 0 0.3rem 0 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 600;
  }
  button,
  select,
  input {
    font: inherit;
    color: var(--text-primary);
    box-sizing: border-box;
    min-width: 0;
  }
  button,
  select,
  input[type='number'] {
    border: 1px solid var(--glass-border);
    border-radius: 0.25rem;
    padding: 0.35rem 0.4rem;
    background: rgb(var(--theme-rgb-surface-card-deep));
    font-size: 0.76rem;
  }
  button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    cursor: pointer;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    white-space: nowrap;
  }
  button:hover,
  button:active {
    transform: none;
  }
  .source-row {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }
  .source-row > select:first-of-type {
    max-width: 10rem;
  }
  .image-choice {
    flex: 1;
    width: 0;
  }
  .upload {
    margin-left: auto;
    border-color: transparent;
    background: transparent;
  }
  select option {
    background: var(--theme-color-surface-card);
  }
  label {
    display: grid;
    gap: 0.25rem;
    text-align: left;
    font-size: 0.7rem;
    color: var(--text-secondary);
  }
  .transform-row {
    display: grid;
    grid-template-columns: auto 7.5rem minmax(5rem, 1fr) auto;
    gap: 0.65rem;
    align-items: end;
    margin-top: 0.65rem;
  }
  .move {
    min-height: 2rem;
  }
  .active {
    border-color: var(--theme-accent-color);
    color: var(--theme-accent-color);
    background: rgba(var(--theme-rgb-accent), 0.1);
  }
  .position {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
  }
  input[type='number'] {
    width: 100%;
  }
  .scale label {
    display: flex;
    justify-content: space-between;
  }
  .scale input {
    width: 100%;
    height: 1.8rem;
    margin: 0;
    accent-color: var(--theme-accent-color);
  }
  output {
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }
  .reset {
    border-color: transparent;
    background: transparent;
    height: 2rem;
    padding: 0.25rem;
  }
  .file-input {
    display: none;
  }
  :is(button, input, select):focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 2px;
  }
  @media (max-width: 57rem) {
    .transform-row {
      grid-template-columns: auto 6.5rem minmax(4rem, 1fr) auto;
      gap: 0.45rem;
    }
    .source-row > select:first-of-type {
      max-width: 8.5rem;
    }
    .upload {
      font-size: 0.72rem;
      padding: 0.3rem;
    }
  }
  @media (max-width: 40rem) {
    .source-row {
      flex-wrap: wrap;
    }
    .image-choice {
      min-width: 6rem;
    }
    .transform-row {
      grid-template-columns: 1fr 1fr auto;
    }
    .scale {
      grid-column: 1/3;
      grid-row: 2;
    }
    .reset {
      grid-column: 3;
      grid-row: 2;
    }
  }
</style>
