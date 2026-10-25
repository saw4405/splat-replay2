<script lang="ts">
  import type { Snippet } from 'svelte';
  interface Field {
    key: string;
    label: string;
  }
  interface Props {
    title: string;
    imageUrl?: string;
    imageSize: [number, number];
    regions?: Record<string, [number, number, number, number]>;
    fields: Field[];
    crop?: [number, number];
    topFieldKeys?: string[];
    seconds?: number;
    minWidth?: string;
    maxWidth?: string;
    children: Snippet<[string]>;
  }
  let {
    title,
    imageUrl,
    imageSize,
    regions = {},
    fields,
    crop,
    topFieldKeys = [],
    seconds,
    minWidth = '0',
    maxWidth = '100%',
    children,
  }: Props = $props();
  let failedImageUrl = $state<string>();
  let orderedFields = $derived(
    [...fields].sort((left, right) => centerX(left.key) - centerX(right.key))
  );
  function centerX(key: string): number {
    const region = regions[key];
    return region ? region[0] + region[2] / 2 : Infinity;
  }
  function sharedRegionNumbers(key: string): number[] {
    const region = regions[key];
    return orderedFields.flatMap((field, index) =>
      region?.every((coordinate, dimension) => coordinate === regions[field.key]?.[dimension])
        ? [index + 1]
        : []
    );
  }
  function displayRegion(
    region: [number, number, number, number]
  ): [number, number, number, number] {
    const padding = imageSize[0] * 0.006;
    const left = Math.max(0, region[0] - padding);
    const top = Math.max(0, region[1] - padding);
    return [
      left,
      top,
      Math.min(imageSize[0], region[0] + region[2] + padding) - left,
      Math.min(imageSize[1], region[1] + region[3] + padding) - top,
    ];
  }
  let cropTop = $derived(crop?.[0] ?? 0);
  let cropBottom = $derived(crop?.[1] ?? imageSize[1]);
  let cropHeight = $derived(cropBottom - cropTop);
  let topFields = $derived(orderedFields.filter((field) => topFieldKeys.includes(field.key)));
  let bottomFields = $derived(orderedFields.filter((field) => !topFieldKeys.includes(field.key)));
  let lineSpace = $derived(imageSize[0] * (topFields.length ? 0.025 : 0.07));
  let topSpace = $derived(topFields.length ? lineSpace : 0);
  let bottomSpace = $derived(bottomFields.length ? lineSpace : 0);
  let markerSize = $derived(imageSize[0] / 50);
</script>

{#snippet callouts(items: Field[])}
  {#if items.length}
    <div
      class="callouts"
      class:split-callouts={topFields.length > 0}
      style:grid-template-columns={`repeat(${items.length}, minmax(0, 1fr))`}
    >
      {#each items as field}
        <div class="callout">
          <span class="field-label"><b>{orderedFields.indexOf(field) + 1}</b> {field.label}</span
          >{@render children(field.key)}{#if !regions[field.key]}<span class="missing"
              >対応位置未取得</span
            >{/if}
        </div>
      {/each}
    </div>
  {/if}
{/snippet}

<section class="evidence-panel" aria-label={title}>
  <header>
    <h4>{title}</h4>
    {#if seconds !== undefined}<span>元動画 {seconds.toFixed(1)}秒</span>{/if}
  </header>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex キーボードでも画像と編集欄を横スクロールできるようにする -->
  <div class="diagram-scroll" tabindex="0" role="region" aria-label={`${title}の画像と編集欄`}>
    <div class="diagram" style:min-width={minWidth} style:max-width={maxWidth}>
      {@render callouts(topFields)}
      {#if imageUrl && failedImageUrl !== imageUrl}
        <div
          class="image-map"
          style:aspect-ratio={`${imageSize[0]} / ${cropHeight + topSpace + bottomSpace}`}
        >
          <a
            style:aspect-ratio={`${imageSize[0]} / ${cropHeight}`}
            style:top={`${(topSpace / (cropHeight + topSpace + bottomSpace)) * 100}%`}
            href={imageUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`${title}の画像を拡大`}
            ><img
              style:transform={`translateY(${(-cropTop / imageSize[1]) * 100}%)`}
              src={imageUrl}
              alt={title}
              onerror={() => (failedImageUrl = imageUrl)}
            /></a
          >
          <svg
            viewBox={`0 ${cropTop - topSpace} ${imageSize[0]} ${cropHeight + topSpace + bottomSpace}`}
            aria-hidden="true"
          >
            {#each orderedFields as field, index}
              {@const region = regions[field.key]}
              {#if region}
                {@const box = displayRegion(region)}
                {@const centerX = box[0] + box[2] / 2}
                {@const isTop = topFieldKeys.includes(field.key)}
                {@const group = isTop ? topFields : bottomFields}
                {@const startY = isTop ? box[1] : box[1] + box[3]}
                {@const edgeY = isTop ? cropTop - topSpace : cropBottom + bottomSpace}
                {@const bendY = isTop
                  ? Math.min(startY, cropTop - topSpace * 0.2)
                  : Math.max(startY, cropBottom + bottomSpace * 0.2)}
                {@const markerY = startY + (isTop ? -1 : 1) * (markerSize + 2)}
                {@const endX = (imageSize[0] * (group.indexOf(field) + 0.5)) / group.length}
                {@const numbers = sharedRegionNumbers(field.key)}
                {#if numbers[0] === index + 1}
                  <rect x={box[0]} y={box[1]} width={box[2]} height={box[3]} />
                {/if}
                <polyline points={`${centerX},${startY} ${centerX},${bendY} ${endX},${edgeY}`} />
                {#if numbers[0] === index + 1}
                  <ellipse
                    cx={centerX}
                    cy={markerY}
                    rx={markerSize * (numbers.length > 1 ? 1.5 : 0.9)}
                    ry={markerSize * 0.9}
                  />
                  <text
                    x={centerX}
                    y={markerY}
                    dy=".35em"
                    text-anchor="middle"
                    font-size={markerSize}>{numbers.join('/')}</text
                  >
                {/if}
              {/if}
            {/each}
          </svg>
        </div>
      {:else}<p class="missing">{title}の画像は未取得です。</p>{/if}
      {@render callouts(bottomFields)}
    </div>
  </div>
</section>

<style>
  .evidence-panel {
    display: grid;
    gap: 0.5rem;
    min-width: 0;
    border-top: 1px solid var(--glass-border);
    padding-top: 1rem;
  }
  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
  }
  h4 {
    font-size: 0.9rem;
    margin: 0;
  }
  header span,
  .missing {
    font-size: 0.75rem;
    color: var(--theme-color-text-secondary);
  }
  .diagram-scroll {
    overflow: auto;
    padding: 0.25rem 0.25rem 0.5rem;
  }
  .image-map {
    position: relative;
    width: 100%;
  }
  .image-map a {
    display: block;
    position: absolute;
    width: 100%;
    overflow: hidden;
  }
  .image-map img {
    display: block;
    position: absolute;
    width: 100%;
    height: auto;
  }
  .image-map svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    overflow: visible;
  }
  rect,
  polyline {
    fill: none;
    stroke: var(--theme-accent-color);
    stroke-width: 1.5;
    vector-effect: non-scaling-stroke;
  }
  ellipse {
    fill: rgba(var(--theme-rgb-surface-card), 0.95);
    stroke: var(--theme-accent-color);
    stroke-width: 1.5;
    vector-effect: non-scaling-stroke;
  }
  text {
    fill: currentColor;
    font-weight: 700;
  }
  .callouts {
    display: grid;
    gap: 0.75rem;
  }
  .split-callouts {
    gap: 0;
  }
  .split-callouts .callout {
    padding-inline: 0.375rem;
  }
  .callout {
    display: grid;
    align-content: start;
    gap: 0.35rem;
    min-width: 0;
  }
  .field-label {
    font-size: 0.75rem;
  }
  .field-label b {
    color: var(--theme-accent-color);
  }
  .missing {
    margin: 0;
  }
  .diagram-scroll:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 1px;
  }
</style>
