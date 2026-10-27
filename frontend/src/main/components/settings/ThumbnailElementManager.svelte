<script lang="ts">
  import { tick, type Snippet } from 'svelte';
  import { Type, Square, ImagePlus, ArrowUp, ArrowDown, Trash2, Eye, EyeOff } from 'lucide-svelte';
  import type { ThumbnailElement } from '../../api/thumbnailDesign';
  let {
    elements,
    selectedId,
    assetsOpen,
    onselect,
    onadd,
    onassets,
    onreorder,
    ondelete,
    children,
  }: {
    elements: ThumbnailElement[];
    selectedId: string;
    assetsOpen: boolean;
    onselect: (id: string) => void;
    onadd: (source: 'text' | 'shape') => void;
    onassets: () => void;
    onreorder: (delta: number) => void;
    ondelete: () => void;
    children?: Snippet;
  } = $props();
  let list = $state<HTMLDivElement>();
  $effect(() => {
    const id = selectedId;
    if (assetsOpen) return;
    void tick().then(() => {
      if (selectedId !== id) return;
      const row = list?.querySelector<HTMLElement>('[aria-pressed="true"]')?.parentElement;
      if (!row || !list) return;
      const bounds = row.getBoundingClientRect();
      const viewport = list.getBoundingClientRect();
      if (bounds.top < viewport.top) list.scrollTop += bounds.top - viewport.top;
      else if (bounds.bottom > viewport.bottom) list.scrollTop += bounds.bottom - viewport.bottom;
    });
  });
  const selected = $derived(elements.find((e) => e.id === selectedId));
</script>

<section class="manager" aria-label="要素の管理">
  <header>
    <h3>要素</h3>
    <span>{elements.length}件</span>
  </header>
  <div class="add-tools" aria-label="要素の追加">
    <button
      type="button"
      disabled={elements.length >= 64}
      onclick={() => onadd('text')}
      aria-label="文字を追加"><Type size={15} />文字</button
    >
    <button
      type="button"
      disabled={elements.length >= 64}
      onclick={() => onadd('shape')}
      aria-label="図形を追加"><Square size={15} />図形</button
    >
    <button
      type="button"
      class:active={assetsOpen}
      onclick={onassets}
      aria-label="画像を追加"
      aria-pressed={assetsOpen}><ImagePlus size={15} />画像</button
    >
  </div>
  {#if assetsOpen}<div class="material-scroll">
      <button class="return" type="button" onclick={onassets}>要素一覧に戻る</button
      >{@render children?.()}
    </div>{:else}
    <div class="layer-list" bind:this={list} role="group" aria-label="要素一覧（上が前面）">
      {#each elements.slice().reverse() as e (e.id)}
        <div class="layer" class:selected={e.id === selectedId}>
          <label class="visibility" title={e.visible ? `${e.name}を非表示` : `${e.name}を表示`}
            ><input
              type="checkbox"
              bind:checked={e.visible}
              aria-label={`${e.name}を表示`}
            />{#if e.visible}<Eye size={15} />{:else}<EyeOff size={15} />{/if}</label
          >
          <button type="button" onclick={() => onselect(e.id)} aria-pressed={e.id === selectedId}
            ><span class="kind" aria-hidden="true"
              >{e.source === 'text' || e.source === 'win_lose' || e.source === 'rate'
                ? 'T'
                : e.source === 'shape'
                  ? '□'
                  : '▧'}</span
            ><span class:muted={!e.visible}>{e.name}</span></button
          >
        </div>
      {/each}
      {#if !elements.length}<p class="empty">文字・図形・画像を追加してください。</p>{/if}
    </div>
  {/if}
  <footer>
    <span class="stack-hint">上が前面</span>
    <button
      type="button"
      title="前面へ"
      aria-label="前面へ"
      disabled={!selected || elements.at(-1)?.id === selectedId}
      onclick={() => onreorder(1)}><ArrowUp size={15} /></button
    >
    <button
      type="button"
      title="背面へ"
      aria-label="背面へ"
      disabled={!selected || elements[0]?.id === selectedId}
      onclick={() => onreorder(-1)}><ArrowDown size={15} /></button
    >
    <button
      type="button"
      class="delete"
      aria-label="要素を削除"
      disabled={!selected}
      onclick={ondelete}><Trash2 size={14} />削除</button
    >
  </footer>
</section>

<style>
  .manager {
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: transparent;
    overflow: hidden;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.8rem 0 0.5rem;
  }
  h3 {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin: 0;
  }
  header > span,
  .stack-hint {
    color: var(--text-secondary);
    font-size: 0.7rem;
  }
  button {
    font: inherit;
    color: var(--text-primary);
    cursor: pointer;
    border: 1px solid var(--glass-border);
    border-radius: 0.25rem;
    background: rgb(var(--theme-rgb-surface-card-deep));
    padding: 0.35rem 0.5rem;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    font-size: 0.78rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
  }
  button:hover {
    transform: none;
  }
  button:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .add-tools {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4rem;
    padding: 0 0.5rem 0.6rem 0;
  }
  .active {
    border-color: var(--theme-accent-color);
    color: var(--theme-accent-color);
  }
  .layer-list,
  .material-scroll {
    overflow: auto;
    min-height: 0;
    flex: 1;
    border-top: 0;
  }
  .material-scroll {
    padding: 0.7rem;
  }
  .return {
    margin-bottom: 0.6rem;
  }
  .layer {
    display: flex;
    align-items: center;
    min-height: 2rem;
    padding: 0 0.65rem;
    border-left: 3px solid transparent;
  }
  .layer.selected {
    background: rgba(var(--theme-rgb-accent), 0.12);
    border-left-color: var(--theme-accent-color);
  }
  .layer > button {
    justify-content: flex-start;
    min-width: 0;
    width: 100%;
    border: 0;
    background: transparent;
    text-align: left;
    padding: 0.4rem;
  }
  .layer > button > span:last-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kind {
    display: inline-flex;
    width: 1rem;
    justify-content: center;
    color: var(--text-secondary);
    flex-shrink: 0;
  }
  .visibility {
    position: relative;
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.8rem;
    color: var(--text-secondary);
    flex-shrink: 0;
  }
  .visibility input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    cursor: pointer;
  }
  .visibility:focus-within {
    outline: 2px solid var(--theme-accent-color);
    border-radius: 0.2rem;
  }
  .muted {
    opacity: 0.5;
  }
  footer {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.5rem 0.5rem 0.5rem 0;
    border-top: 0;
  }
  .stack-hint {
    margin-right: auto;
  }
  .delete {
    margin-left: 0.3rem;
  }
  .empty {
    padding: 0.5rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }
  button:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: -2px;
  }
</style>
