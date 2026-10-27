<script lang="ts">
  import { tick } from 'svelte';
  import ThumbnailTemplateHints from './ThumbnailTemplateHints.svelte';
  import {
    thumbnailAssetUrl,
    type ThumbnailAsset,
    type ThumbnailElement,
  } from '../../api/thumbnailDesign';
  let {
    element: e,
    assets,
    onpick,
    focusRequest = 0,
    variables = {},
  }: {
    element: ThumbnailElement;
    assets: ThumbnailAsset[];
    focusRequest?: number;
    variables?: Record<string, string | number>;
    onpick: (field: 'color' | 'outline_color') => void;
  } = $props();
  let textInput = $state<HTMLTextAreaElement>();
  $effect(() => {
    const request = focusRequest;
    if (!request) return;
    void tick().then(() => {
      textInput?.focus();
    });
  });
  const isText = $derived(['text', 'win_lose', 'rate'].includes(e.source));
  function resize(value: number, field: 'width' | 'height'): void {
    if (!Number.isFinite(value) || value < 1) return;
    if (e.source !== 'shape') {
      if (field === 'width')
        e.height = Math.max(1, Math.round(((e.height || 135) * value) / (e.width || 532)));
      else e.width = Math.max(1, Math.round(((e.width || 532) * value) / (e.height || 135)));
    }
    e[field] = value;
  }
  function chooseAsset(value: string): void {
    e.asset = value;
    const target = e;
    const image = new Image();
    image.onload = () => {
      if (target.asset === value) {
        target.width = 400;
        target.height = Math.max(1, Math.round((400 * image.naturalHeight) / image.naturalWidth));
      }
    };
    image.src = thumbnailAssetUrl(value);
  }
</script>

<div class="inspector">
  {#if isText}
    <label
      >{e.source === 'text' ? '文字内容' : 'テンプレート'}<textarea
        bind:this={textInput}
        bind:value={e.template}
        rows="2"
        maxlength="1000"
        placeholder="表示したい文字を入力"
      ></textarea></label
    >
    <ThumbnailTemplateHints {variables} />
    <div class="font-row">
      <label
        >フォント<select bind:value={e.font}
          >{#each assets.filter((a) => a.kind === 'font') as font}<option value={font.id}
              >{font.name}</option
            >{/each}</select
        ></label
      >
      <label>文字サイズ<input type="number" bind:value={e.font_size} min="8" max="300" /></label>
    </div>
    {#if e.source === 'rate'}<label class="check"
        ><input type="checkbox" bind:checked={e.auto_color} />マッチに応じて文字色を変える</label
      >{/if}
  {:else}
    <div class="pair">
      <label
        >幅<input
          type="number"
          value={e.width}
          min="1"
          max="3840"
          oninput={(event) => resize(event.currentTarget.valueAsNumber, 'width')}
        /></label
      ><label
        >高さ<input
          type="number"
          value={e.height}
          min="1"
          max="2160"
          oninput={(event) => resize(event.currentTarget.valueAsNumber, 'height')}
        /></label
      >
    </div>
    {#if e.source === 'shape'}
      <label
        >図形<select bind:value={e.shape}
          ><option value="rectangle">矩形</option><option value="rounded_rectangle">角丸矩形</option
          ><option value="ellipse">楕円</option></select
        ></label
      >
      {#if e.shape === 'rounded_rectangle'}<label
          >角丸の半径<input type="number" bind:value={e.radius} min="0" max="1000" /></label
        >{/if}
    {/if}
    {#if e.source === 'image' || e.source === 'overlay'}<label
        >画像素材<select
          value={e.asset}
          onchange={(event) => chooseAsset(event.currentTarget.value)}
          ><option value="">画像を選択</option
          >{#each assets.filter((a) => a.kind === 'image') as image}<option value={image.id}
              >{image.name}</option
            >{/each}</select
        ></label
      >{/if}
  {/if}
  {#if isText || e.source === 'shape'}
    <div class="color">
      <label>色<input type="color" bind:value={e.color} /></label><button
        type="button"
        onclick={() => onpick('color')}
        disabled={e.source === 'rate' && e.auto_color}>スポイト</button
      >
    </div>
  {/if}
  {#if isText || e.source === 'shape' || e.source === 'highlights'}
    <label>縁の太さ<input type="number" bind:value={e.outline_width} min="0" max="20" /></label>
    <div class="color">
      <label>縁の色<input type="color" bind:value={e.outline_color} /></label><button
        type="button"
        onclick={() => onpick('outline_color')}>縁のスポイト</button
      >
    </div>
  {/if}
  <fieldset class="position">
    <legend>位置 <span>px</span></legend>
    <div class="pair">
      <label>X<input type="number" bind:value={e.x} min="-7680" max="7680" /></label><label
        >Y<input type="number" bind:value={e.y} min="-4320" max="4320" /></label
      >
    </div>
    {#if isText}
      <label class="check"
        ><input type="checkbox" bind:checked={e.center} />指定位置を文字の中心にする</label
      >
    {/if}
  </fieldset>
  <div class="identity">
    <label>要素名<input bind:value={e.name} maxlength="80" /></label><label class="check"
      ><input type="checkbox" bind:checked={e.visible} />表示する</label
    >
    <label
      >不透明度 {Math.round(e.opacity * 100)}%<input
        type="range"
        bind:value={e.opacity}
        min="0"
        max="1"
        step="0.01"
      /></label
    >
  </div>
</div>

<style>
  .font-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 5rem;
    gap: 0.6rem;
  }
  .position {
    border: 0;
    margin: 0;
    padding: 0;
  }
  legend {
    font-size: 0.78rem;
    padding: 0;
    margin-bottom: 0.4rem;
  }
  legend span {
    color: var(--text-secondary);
    font-size: 0.7rem;
  }
  textarea {
    resize: vertical;
    min-height: 4rem;
    line-height: 1.5;
  }
  .identity {
    border-top: 1px solid var(--glass-border);
    padding-top: 0.6rem;
  }
  .identity label {
    margin-top: 0.6rem;
  }
  :is(input, select, textarea, button):focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 2px;
  }
  .inspector {
    display: grid;
    gap: 0.7rem;
  }
  label {
    display: grid;
    gap: 0.3rem;
    font-size: 0.78rem;
    text-align: left;
  }
  input,
  select,
  textarea,
  button {
    font: inherit;
    color: var(--text-primary);
    background: rgb(var(--theme-rgb-surface-card-deep));
    border: 1px solid var(--glass-border);
    border-radius: 0.25rem;
    padding: 0.4rem;
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
  }
  select option {
    background: var(--theme-color-surface-card);
  }
  input[type='color'] {
    width: 3.5rem;
    height: 2.2rem;
  }
  .pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
  }
  .check,
  .color {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .color label {
    flex: 1;
  }
  button {
    cursor: pointer;
  }
</style>
