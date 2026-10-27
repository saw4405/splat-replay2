<script lang="ts">
  import type {
    ThumbnailDesign,
    ThumbnailElement,
    ThumbnailBounds,
  } from '../../api/thumbnailDesign';
  interface Props {
    layout: Record<string, ThumbnailBounds>;
    design: ThumbnailDesign;
    imageUrl: string;
    selectedId: string;
    onselect: (id: string) => void;
    onedittext?: (id: string) => void;
    backgroundMoving?: boolean;
    onmove: (id: string, x: number, y: number) => void;
    onsample: (color: string) => void;
    picking: boolean;
  }
  let {
    layout,
    design,
    imageUrl,
    selectedId,
    onselect,
    onmove,
    onsample,
    picking,
    onedittext,
    backgroundMoving = false,
  }: Props = $props();
  const selectedBox = $derived(!backgroundMoving ? layout[selectedId] : null);
  let surface: HTMLDivElement;
  let preview = $state<HTMLImageElement>();
  let drag = $state<{
    id: string;
    startX: number;
    startY: number;
    x: number;
    y: number;
    dx: number;
    dy: number;
  } | null>(null);

  function start(event: PointerEvent, e: Pick<ThumbnailElement, 'id' | 'x' | 'y'>): void {
    if (picking || event.button !== 0) return;
    if (e.id !== 'background') onselect(e.id);
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    drag = { id: e.id, startX: event.clientX, startY: event.clientY, x: e.x, y: e.y, dx: 0, dy: 0 };
  }
  function move(event: PointerEvent): void {
    if (!drag) return;
    const rect = surface.getBoundingClientRect();
    drag.dx = Math.round(((event.clientX - drag.startX) * 1920) / rect.width);
    drag.dy = Math.round(((event.clientY - drag.startY) * 1080) / rect.height);
  }
  function stop(): void {
    if (!drag) return;
    onmove(
      drag.id,
      Math.max(-7680, Math.min(7680, drag.x + drag.dx)),
      Math.max(-4320, Math.min(4320, drag.y + drag.dy))
    );
    drag = null;
  }
  function sample(event: MouseEvent): void {
    if (!picking || !preview?.naturalWidth) return;
    const rect = surface.getBoundingClientRect();
    const canvas = document.createElement('canvas');
    canvas.width = preview.naturalWidth;
    canvas.height = preview.naturalHeight;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(preview, 0, 0);
    const pixel = context.getImageData(
      Math.min(
        canvas.width - 1,
        Math.max(0, Math.floor(((event.clientX - rect.left) * canvas.width) / rect.width))
      ),
      Math.min(
        canvas.height - 1,
        Math.max(0, Math.floor(((event.clientY - rect.top) * canvas.height) / rect.height))
      ),
      1,
      1
    ).data;
    onsample(
      '#' +
        [...pixel]
          .slice(0, 3)
          .map((c) => c.toString(16).padStart(2, '0'))
          .join('')
    );
  }
</script>

<div class="preview" bind:this={surface}>
  {#if imageUrl}<img
      bind:this={preview}
      src={imageUrl}
      alt="サンプルデータによるサムネイルのプレビュー"
      draggable="false"
    />{/if}
  {#if !backgroundMoving && !picking}<button
      type="button"
      class="canvas-clear"
      aria-label="要素の選択を解除"
      onclick={() => onselect('')}
    ></button>{/if}
  {#each design.elements.filter((e) => !backgroundMoving && e.visible && layout[e.id]) as e (e.id)}
    {@const b = layout[e.id]}
    <button
      type="button"
      class="element"
      class:selected={e.id === selectedId}
      style:left={`${b.x / 19.2}%`}
      style:top={`${b.y / 10.8}%`}
      style:width={`${b.width / 19.2}%`}
      style:height={`${b.height / 10.8}%`}
      style:transform={drag?.id === e.id
        ? `translate(${(drag.dx / b.width) * 100}%, ${(drag.dy / b.height) * 100}%)`
        : ''}
      aria-label={`${e.name}の位置を調整`}
      title={`${e.name}：ドラッグで移動。矢印キーでも調整できます`}
      ondblclick={() => {
        if (['text', 'win_lose', 'rate'].includes(e.source)) onedittext?.(e.id);
      }}
      onpointerdown={(event) => start(event, e)}
      onpointermove={move}
      onpointerup={stop}
      onpointercancel={() => (drag = null)}
      onkeydown={(event) => {
        if (event.key === 'Enter' && ['text', 'win_lose', 'rate'].includes(e.source))
          onedittext?.(e.id);
        const step = event.shiftKey ? 10 : 1;
        const delta: Record<string, [number, number]> = {
          ArrowLeft: [-step, 0],
          ArrowRight: [step, 0],
          ArrowUp: [0, -step],
          ArrowDown: [0, step],
        };
        if (delta[event.key]) {
          event.preventDefault();
          onmove(e.id, e.x + delta[event.key][0], e.y + delta[event.key][1]);
        }
      }}
    ></button>
  {/each}
  {#if selectedBox && design.elements.some((e) => e.id === selectedId && e.visible)}<div
      class="selection-outline"
      aria-hidden="true"
      style:left={`${(selectedBox.x + (drag?.id === selectedId ? drag.dx : 0)) / 19.2}%`}
      style:top={`${(selectedBox.y + (drag?.id === selectedId ? drag.dy : 0)) / 10.8}%`}
      style:width={`${selectedBox.width / 19.2}%`}
      style:height={`${selectedBox.height / 10.8}%`}
    ></div>{/if}
  {#if backgroundMoving}<button
      type="button"
      class="background-move"
      aria-label="背景の位置を調整"
      onpointerdown={(event) =>
        start(event, { id: 'background', x: design.background.x, y: design.background.y })}
      onpointermove={move}
      onpointerup={stop}
      onpointercancel={() => (drag = null)}
      onkeydown={(event) => {
        const step = event.shiftKey ? 10 : 1;
        const directions: Record<string, [number, number]> = {
          ArrowLeft: [-step, 0],
          ArrowRight: [step, 0],
          ArrowUp: [0, -step],
          ArrowDown: [0, step],
        };
        const delta = directions[event.key];
        if (delta) {
          event.preventDefault();
          onmove('background', design.background.x + delta[0], design.background.y + delta[1]);
        }
      }}
    ></button>{/if}
  {#if picking}<button
      type="button"
      class="picker"
      aria-label="プレビューから色を取得"
      onclick={sample}
    ></button>{/if}
</div>

<style>
  .preview {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: var(--glass-bg-strong);
    outline: 1px solid var(--glass-border);
  }
  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    pointer-events: none;
  }
  .element {
    position: absolute;
    padding: 0;
    border: 1px solid transparent;
    background: transparent;
    touch-action: none;
    cursor: move;
    min-width: 8px;
    min-height: 8px;
  }
  .element,
  .picker,
  .canvas-clear,
  .background-move {
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    box-shadow: none;
    border-radius: 0;
    transition: none;
    filter: none;
  }
  .canvas-clear,
  .canvas-clear:hover,
  .canvas-clear:focus,
  .canvas-clear:active,
  .background-move:hover,
  .background-move:active,
  .background-move:focus,
  .element:focus,
  .element:hover,
  .element:active,
  .element:focus-visible,
  .picker:hover,
  .picker:active,
  .picker:focus-visible {
    background: transparent;
    box-shadow: none;
    transform: none;
  }
  .element:hover,
  .element:focus-visible {
    border-color: var(--theme-accent-color);
    outline: none;
  }
  .selection-outline {
    position: absolute;
    pointer-events: none;
    z-index: 3;
    border: 2px solid var(--theme-color-white);
    outline: 1px solid var(--theme-color-black);
    box-shadow:
      inset 0 0 0 1px var(--theme-color-black),
      0 0 0 2px var(--theme-color-white);
    box-sizing: border-box;
  }
  .canvas-clear {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
    padding: 0;
    cursor: default;
  }
  .canvas-clear:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: -2px;
  }
  .background-move {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    border: 0;
    padding: 0;
    border-radius: 0;
    cursor: grab;
    touch-action: none;
    box-shadow:
      inset 0 0 0 2px var(--theme-color-white),
      inset 0 0 0 4px var(--theme-color-black);
  }
  .background-move:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: -2px;
  }
  .background-move:active {
    cursor: grabbing;
  }
  .background-move:hover {
    background: transparent;
    transform: none;
  }

  .picker {
    z-index: 2;
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    border: 2px solid var(--theme-accent-color);
    cursor: crosshair;
  }
</style>
