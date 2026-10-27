<script lang="ts">
  import { onDestroy, onMount, untrack, tick } from 'svelte';
  import { Undo2, Redo2 } from 'lucide-svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import {
    deleteThumbnail,
    getThumbnailCatalog,
    newThumbnailElement,
    renderThumbnail,
    thumbnailAssetUrl,
    uploadThumbnail,
    type ThumbnailCatalog,
    type ThumbnailDesign,
    type ThumbnailElement,
    type ThumbnailBounds,
  } from '../../api/thumbnailDesign';
  import ThumbnailCanvas from './ThumbnailCanvas.svelte';
  import ThumbnailElementInspector from './ThumbnailElementInspector.svelte';
  import ThumbnailBackgroundPanel from './ThumbnailBackgroundPanel.svelte';
  import ThumbnailElementManager from './ThumbnailElementManager.svelte';

  let {
    open = $bindable(false),
    design,
    onapply,
  }: {
    open?: boolean;
    design: ThumbnailDesign;
    onapply: (design: ThumbnailDesign) => void;
  } = $props();
  let draft = $state<ThumbnailDesign>(
    untrack(() => JSON.parse(JSON.stringify(design)) as ThumbnailDesign)
  );
  let catalog = $state<ThumbnailCatalog | null>(null);
  let selectedId = $state(untrack(() => draft.elements[0]?.id ?? ''));
  let scenario = $state('x');
  let imageUrl = $state('');
  let layout = $state<Record<string, ThumbnailBounds>>({});
  let panel = $state<'layers' | 'assets'>('layers');
  let zoom = $state('fit');
  let viewportWidth = $state(0);
  let viewportHeight = $state(0);
  const fittedWidth = $derived(
    Math.max(1, Math.min(viewportWidth - 32, ((viewportHeight - 40) * 16) / 9))
  );
  let backgroundMoving = $state(false);
  let textFocusRequest = $state(0);
  let propertiesScroll = $state<HTMLDivElement>();
  $effect(() => {
    const id = selectedId;
    const request = textFocusRequest;
    void tick().then(() => {
      if (propertiesScroll && selectedId === id && textFocusRequest === request)
        propertiesScroll.scrollTop = 0;
    });
  });
  let history = $state<string[]>([untrack(() => JSON.stringify(draft))]);
  let historyIndex = $state(0);
  let confirmedImage = $state(false);
  let busy = $state(false);
  let rendering = $state(false);
  let error = $state('');
  let picker = $state<'color' | 'outline_color' | null>(null);
  let selectedAsset = $state('');
  let resetConfirmation = $state(false);
  let deleteConfirmation = $state(false);
  let controller: AbortController | null = null;
  let requestId = 0;
  let disposed = false;
  const selected = $derived(draft.elements.find((e) => e.id === selectedId));
  const referenced = $derived(
    new Set([draft.background.asset, ...draft.elements.map((e) => e.asset)])
  );
  const images = $derived(catalog?.assets.filter((a) => a.kind === 'image') ?? []);
  const selectedMaterial = $derived(images.find((a) => a.id === selectedAsset));
  const serialized = $derived(JSON.stringify(draft));

  onMount(() => {
    void reloadCatalog();
  });
  onDestroy(() => {
    disposed = true;
    requestId++;
    controller?.abort();
  });

  $effect(() => {
    const snapshot = serialized;
    const sample = scenario;
    if (!catalog || confirmedImage || busy) return;
    const timer = setTimeout(() => {
      void generate(JSON.parse(snapshot) as ThumbnailDesign, sample, false);
    }, 250);
    return () => clearTimeout(timer);
  });

  async function reloadCatalog(): Promise<void> {
    try {
      catalog = await getThumbnailCatalog();
    } catch (cause) {
      showError(cause);
    }
  }
  function showError(cause: unknown): void {
    if (!disposed)
      error =
        cause instanceof Error ? cause.message : '処理に失敗しました。もう一度お試しください。';
  }
  async function generate(
    snapshot: ThumbnailDesign,
    sample: string,
    confirmation: boolean
  ): Promise<void> {
    if (!confirmation && (busy || confirmedImage)) return;
    controller?.abort();
    controller = new AbortController();
    const current = ++requestId;
    rendering = true;
    error = '';
    try {
      const result = await renderThumbnail(snapshot, sample, controller.signal);
      if (disposed || current !== requestId) return;
      if (JSON.stringify(snapshot) !== serialized || sample !== scenario) return;
      imageUrl = result.image;
      layout = result.layout;
      if (confirmation) confirmedImage = true;
    } catch (cause) {
      if (!(cause instanceof DOMException && cause.name === 'AbortError') && current === requestId)
        showError(cause);
    } finally {
      if (current === requestId) rendering = false;
    }
  }
  async function apply(): Promise<void> {
    if (busy) return;
    if (confirmedImage) {
      onapply(JSON.parse(serialized) as ThumbnailDesign);
      open = false;
      return;
    }
    busy = true;
    picker = null;
    try {
      await generate(JSON.parse(serialized) as ThumbnailDesign, scenario, true);
    } finally {
      busy = false;
    }
  }
  function add(source: 'text' | 'shape' | 'image'): void {
    if (draft.elements.length >= 64) return;
    panel = 'layers';
    backgroundMoving = false;
    const e = newThumbnailElement(source);
    if (source === 'text')
      e.font =
        catalog?.assets.find(
          (a) => a.kind === 'font' && a.id.startsWith('system-font/') && a.id !== 'system-font/sans'
        )?.id || e.font;
    if (source === 'image') e.asset = selectedAsset || images[0]?.id || '';
    draft.elements.push(e);
    selectedId = e.id;
    if (source === 'text') textFocusRequest++;
    if (source === 'image' && e.asset) setImage(draft.elements[draft.elements.length - 1], e.asset);
  }
  function setImage(e: ThumbnailElement, id: string): void {
    e.asset = id;
    const image = new Image();
    image.onload = () => {
      if (!disposed && e.asset === id) {
        e.width = 400;
        e.height = Math.max(1, Math.round((400 * image.naturalHeight) / image.naturalWidth));
      }
    };
    image.src = thumbnailAssetUrl(id);
  }
  function move(id: string, x: number, y: number): void {
    if (id === 'background') {
      draft.background.x = x;
      draft.background.y = y;
      return;
    }
    const e = draft.elements.find((e) => e.id === id);
    if (e) {
      e.x = x;
      e.y = y;
    }
  }
  function reorder(delta: number): void {
    const index = draft.elements.findIndex((e) => e.id === selectedId);
    const next = index + delta;
    if (index < 0 || next < 0 || next >= draft.elements.length) return;
    const [e] = draft.elements.splice(index, 1);
    draft.elements.splice(next, 0, e);
  }
  async function upload(
    file: File | undefined,
    destination: 'asset' | 'background' = 'asset'
  ): Promise<void> {
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {
      error = '画像は20MB以下にしてください。';
      return;
    }
    busy = true;
    error = '';
    try {
      selectedAsset = await uploadThumbnail(file);
      await reloadCatalog();
      if (destination === 'background') {
        draft.background.source = 'image';
        draft.background.asset = selectedAsset;
        backgroundMoving = true;
      }
    } catch (cause) {
      showError(cause);
    } finally {
      busy = false;
    }
  }
  async function removeAsset(): Promise<void> {
    busy = true;
    error = '';
    try {
      await deleteThumbnail(selectedAsset, JSON.parse(serialized) as ThumbnailDesign);
      selectedAsset = '';
      deleteConfirmation = false;
      await reloadCatalog();
    } catch (cause) {
      showError(cause);
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    const snapshot = serialized;
    untrack(() => {
      if (history[historyIndex] === snapshot) return;
      history = [...history.slice(0, historyIndex + 1), snapshot].slice(-80);
      historyIndex = history.length - 1;
    });
  });
  function travel(delta: number): void {
    const next = historyIndex + delta;
    if (next < 0 || next >= history.length) return;
    historyIndex = next;
    draft = JSON.parse(history[next]) as ThumbnailDesign;
    picker = null;
  }
  function removeSelected(): void {
    const index = draft.elements.findIndex((e) => e.id === selectedId);
    if (index < 0) return;
    draft.elements.splice(index, 1);
    selectedId = draft.elements[Math.min(index, draft.elements.length - 1)]?.id ?? '';
  }
  function select(id: string): void {
    textFocusRequest = 0;
    selectedId = id;
    picker = null;
    backgroundMoving = false;
  }
  function editText(id: string): void {
    selectedId = id;
    picker = null;
    backgroundMoving = false;
    textFocusRequest++;
  }
  function shortcuts(event: KeyboardEvent): void {
    if (!open || confirmedImage || busy) return;
    if (event.key === 'Escape') {
      picker = null;
      backgroundMoving = false;
      return;
    }
    if (
      event.target instanceof HTMLElement &&
      event.target.closest('input, textarea, select, [contenteditable="true"]')
    )
      return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
      event.preventDefault();
      travel(event.shiftKey ? 1 : -1);
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
      event.preventDefault();
      travel(1);
    }
    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      removeSelected();
    }
  }
</script>

<svelte:window onkeydown={shortcuts} />
<BaseDialog
  bind:open
  title="サムネイルデザイン"
  titleId="thumbnail-design-title"
  maxWidth="100rem"
  minHeight="90vh"
  maxHeight="96vh"
  primaryButtonText={confirmedImage ? 'このデザインを使う' : '適用'}
  secondaryButtonText="キャンセル"
  disablePrimaryButton={busy || !catalog}
  disableSecondaryButton={busy}
  onPrimaryClick={apply}
>
  {#snippet header()}
    <div class="dialog-heading">
      <h2 id="thumbnail-design-title">サムネイルデザイン</h2>
      <div class="history-tools">
        <button
          type="button"
          aria-label="元に戻す"
          title="元に戻す（⌘/Ctrl＋Z）"
          disabled={confirmedImage || busy || historyIndex === 0}
          onclick={() => travel(-1)}><Undo2 size={17} /></button
        ><button
          type="button"
          aria-label="やり直す"
          title="やり直す（⌘/Ctrl＋Shift＋Z）"
          disabled={confirmedImage || busy || historyIndex >= history.length - 1}
          onclick={() => travel(1)}><Redo2 size={17} /></button
        >
      </div>
    </div>
  {/snippet}
  {#if confirmedImage}
    <div class="confirmation">
      <h3>生成画像を確認</h3>
      <p>このデザインを使う場合は、親の設定画面で「保存」してください。</p>
      <img src={imageUrl} alt="実際の生成処理によるサンプルサムネイル" /><button
        type="button"
        onclick={() => (confirmedImage = false)}>編集に戻る</button
      >
    </div>
  {:else if catalog}
    <fieldset class="editor" disabled={busy}>
      <div class="visual-column">
        <section class="workspace" aria-label="サムネイルプレビュー">
          <header class="preview-controls">
            <label
              >表示を確認<select aria-label="表示パターン" bind:value={scenario}
                ><option value="x">Xマッチ</option><option value="event">イベントマッチ</option
                ><option value="regular">レートなし</option><option value="anarchy"
                  >バンカラマッチ</option
                ><option value="single">1試合</option></select
              ></label
            >
            {#if rendering}<span class="rendering" role="status">更新中…</span>{/if}
            <label class="zoom-control"
              >表示倍率<select aria-label="表示倍率" bind:value={zoom}
                ><option value="fit">画面に合わせる</option><option value="50">50%</option><option
                  value="100">100%</option
                ><option value="150">150%</option><option value="200">200%</option></select
              ></label
            >
          </header>
          <div
            class="canvas-scroll"
            bind:clientWidth={viewportWidth}
            bind:clientHeight={viewportHeight}
          >
            <button
              type="button"
              class="workspace-clear"
              aria-label="プレビューの余白で選択を解除"
              disabled={backgroundMoving || picker !== null}
              onclick={() => select('')}
            ></button>
            <div
              class="canvas-size"
              style:width={zoom === 'fit' ? `${fittedWidth}px` : `${(1920 * Number(zoom)) / 100}px`}
            >
              <ThumbnailCanvas
                design={draft}
                {layout}
                {imageUrl}
                {selectedId}
                onselect={select}
                onedittext={editText}
                onmove={move}
                {backgroundMoving}
                picking={picker !== null}
                onsample={(color) => {
                  if (selected && picker) {
                    selected[picker] = color;
                    if (picker === 'color') selected.auto_color = false;
                  }
                  picker = null;
                }}
              />
            </div>
          </div>
          <div class="canvas-status">
            <span
              >{picker
                ? 'プレビューの色をクリック'
                : backgroundMoving
                  ? 'ドラッグで背景を移動 · Escで終了'
                  : 'ドラッグで移動 · 文字はダブルクリックで入力'}</span
            >
          </div>
        </section>
        <ThumbnailBackgroundPanel
          background={draft.background}
          {images}
          moving={backgroundMoving}
          onmove={() => {
            backgroundMoving = !backgroundMoving;
            picker = null;
          }}
          onupload={(file) => void upload(file, 'background')}
        />
      </div>
      <div class="controls-column">
        <ThumbnailElementManager
          elements={draft.elements}
          {selectedId}
          assetsOpen={panel === 'assets'}
          onselect={select}
          onadd={add}
          onassets={() => (panel = panel === 'assets' ? 'layers' : 'assets')}
          onreorder={reorder}
          ondelete={removeSelected}
        >
          <section class="asset-browser" aria-label="画像素材">
            <p class="hint">追加・削除はすぐに反映されます。設定をキャンセルしても戻りません。</p>
            <label
              >画像をアップロード<input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={busy}
                onchange={(event) => {
                  void upload(event.currentTarget.files?.[0]);
                  event.currentTarget.value = '';
                }}
              /></label
            ><label
              >画像素材<select aria-label="画像素材" bind:value={selectedAsset}
                ><option value="">素材を選択</option>{#each images as a}<option value={a.id}
                    >{a.name}{a.protected ? '（同梱）' : ''}</option
                  >{/each}</select
              ></label
            >{#if selectedAsset}<img
                class="asset-preview"
                src={thumbnailAssetUrl(selectedAsset)}
                alt="選択中の素材"
              />
              <div class="toolbar">
                <button
                  type="button"
                  onclick={() => {
                    draft.background.asset = selectedAsset;
                    draft.background.source = 'image';
                  }}>背景に使う</button
                ><button type="button" onclick={() => add('image')}>要素として追加</button><button
                  type="button"
                  disabled={busy ||
                    !selectedMaterial ||
                    selectedMaterial.protected ||
                    referenced.has(selectedAsset)}
                  onclick={() => (deleteConfirmation = true)}>画像ファイルを削除</button
                >
              </div>
              {#if referenced.has(selectedAsset)}<p class="hint">
                  編集中のデザインで使用しています。
                </p>{/if}{#if deleteConfirmation}<p>選択した画像ファイルを削除します。</p>
                <button type="button" disabled={busy} onclick={() => void removeAsset()}
                  >削除する</button
                ><button type="button" onclick={() => (deleteConfirmation = false)}
                  >削除しない</button
                >{/if}{/if}
          </section>
        </ThumbnailElementManager>
        <section class="properties-panel" aria-label="選択した要素の編集">
          <header class="section-heading">
            <h3>プロパティ</h3>
          </header>
          <div class="properties-scroll" bind:this={propertiesScroll}>
            {#if selected}
              <ThumbnailElementInspector
                element={selected}
                assets={catalog.assets}
                variables={catalog.variables}
                focusRequest={textFocusRequest}
                onpick={(field) => {
                  picker = field;
                  backgroundMoving = false;
                }}
              />
            {:else}<p class="empty">
                要素一覧またはプレビューで、編集する要素を選択してください。
              </p>{/if}
          </div>
        </section>
      </div>
    </fieldset>
  {:else}<p role="status">素材を読み込んでいます…</p>{/if}
  {#snippet footerStatus()}<div class="footer-note">
      {#if catalog && !confirmedImage}
        <div class="reset-design">
          <button type="button" onclick={() => (resetConfirmation = !resetConfirmation)}
            >初期デザインに戻す</button
          >{#if resetConfirmation}<div class="reset-confirmation">
              <p>編集中のデザインを初期状態に戻します。</p>
              <button
                type="button"
                onclick={() => {
                  draft = JSON.parse(JSON.stringify(catalog?.default_design)) as ThumbnailDesign;
                  selectedId = draft.elements[0]?.id ?? '';
                  backgroundMoving = false;
                  resetConfirmation = false;
                }}>初期状態に戻す</button
              ><button type="button" onclick={() => (resetConfirmation = false)}>戻さない</button>
            </div>{/if}
        </div>
      {/if}{#if error}<p class="error" role="alert">{error}</p>{/if}
    </div>{/snippet}
</BaseDialog>

<style>
  :global(.dialog-container[aria-labelledby='thumbnail-design-title']) {
    height: 96vh;
  }
  :global(.dialog-container[aria-labelledby='thumbnail-design-title'] > .dialog-header) {
    padding: 0.9rem 1.25rem;
  }
  :global(.dialog-container[aria-labelledby='thumbnail-design-title'] > .dialog-body) {
    padding: 0 1.25rem;
  }
  :global(.dialog-container[aria-labelledby='thumbnail-design-title'] > .dialog-footer) {
    padding: 0.85rem 1.25rem;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 1rem;
  }
  .dialog-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    gap: 1rem;
  }
  .dialog-heading h2 {
    font-size: 1.15rem;
  }
  .history-tools {
    display: flex;
    gap: 0.4rem;
  }
  .editor {
    border: 0;
    margin: 0;
    padding: 0;
    min-height: 0;
    min-width: 0;
    flex: 1;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 20rem;
    gap: 1.25rem;
  }
  .visual-column {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
  }
  .controls-column {
    display: grid;
    grid-template-rows: minmax(10rem, 0.65fr) minmax(18rem, 1.35fr);
    min-height: 0;
    min-width: 0;
    border-left: 1px solid var(--glass-border);
    padding-left: 1rem;
  }
  .workspace,
  .properties-panel {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
  }
  .workspace {
    flex: 1;
  }
  .preview-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem 0.75rem;
    padding: 0.8rem 0;
    flex-shrink: 0;
  }
  .preview-controls label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.72rem;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .preview-controls select {
    padding: 0.3rem 0.4rem;
    font-size: 0.75rem;
    max-width: 9rem;
  }
  .zoom-control {
    margin-left: auto;
  }
  .rendering {
    color: var(--text-secondary);
    font-size: 0.7rem;
  }
  .canvas-scroll {
    position: relative;
    flex: 1;
    display: grid;
    place-items: center;
    min-height: 0;
    overflow: auto;
    padding: 1rem;
    background: rgb(var(--theme-rgb-black));
  }
  .canvas-size {
    position: relative;
    flex: none;
    min-width: 0;
  }
  .workspace-clear {
    position: absolute;
    inset: 0;
    border: 0;
    border-radius: 0;
    padding: 0;
    width: 100%;
    height: 100%;
  }
  .workspace-clear,
  .workspace-clear:hover,
  .workspace-clear:active,
  .workspace-clear:focus {
    background: transparent;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    filter: none;
    transform: none;
    transition: none;
    cursor: default;
  }
  .workspace-clear:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: -2px;
  }
  .canvas-status {
    padding: 0.45rem 0;
    font-size: 0.7rem;
    color: var(--text-secondary);
    flex-shrink: 0;
    min-height: 1.1rem;
  }
  .section-heading {
    display: flex;
    align-items: center;
    padding: 0.85rem 0 0.6rem;
    flex-shrink: 0;
  }
  h3 {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 600;
    text-align: left;
    color: var(--text-secondary);
  }
  .properties-panel {
    border-top: 1px solid var(--glass-border);
  }
  .properties-scroll {
    min-height: 0;
    overflow: auto;
    padding: 0 0.5rem 1rem 0;
  }
  button,
  input,
  select {
    font: inherit;
    color: var(--text-primary);
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
  }
  button,
  select {
    padding: 0.4rem 0.55rem;
    border: 1px solid var(--glass-border);
    border-radius: 0.25rem;
    background: rgb(var(--theme-rgb-surface-card-deep));
    font-size: 0.78rem;
  }
  button {
    cursor: pointer;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
  button:hover,
  button:active {
    transform: none;
  }
  button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  select option {
    background: var(--theme-color-surface-card);
  }
  .history-tools button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-color: transparent;
    background: transparent;
  }
  :is(button, input, select):focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 2px;
  }
  .footer-note {
    min-width: 0;
  }
  .reset-design {
    width: fit-content;
    position: relative;
  }
  .reset-design > button {
    border: 0;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.72rem;
    padding-left: 0;
  }
  .reset-confirmation {
    position: absolute;
    bottom: 100%;
    left: 0;
    width: 17rem;
    padding: 0.8rem;
    border: 1px solid var(--glass-border);
    background: var(--theme-color-surface-card);
    z-index: 10;
    border-radius: 0.25rem;
    box-shadow: 0 4px 20px rgba(var(--theme-rgb-black), 0.6);
  }
  .asset-browser {
    display: grid;
    gap: 0.6rem;
    font-size: 0.75rem;
  }
  .asset-browser label {
    display: grid;
    gap: 0.3rem;
  }
  .asset-browser input,
  .asset-browser select {
    width: 100%;
  }
  .asset-preview {
    width: 100%;
    max-height: 6rem;
    object-fit: contain;
    background: rgba(var(--theme-rgb-black), 0.3);
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }
  .hint,
  .empty {
    font-size: 0.75rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
  }
  .error {
    margin: 0.35rem 0 0;
    color: var(--theme-status-danger-soft);
    font-size: 0.75rem;
  }
  .confirmation {
    overflow: auto;
  }
  .confirmation img {
    width: 100%;
    max-height: 70vh;
    object-fit: contain;
    display: block;
    margin-bottom: 1rem;
  }
  @media (max-width: 70rem) {
    .editor {
      grid-template-columns: minmax(0, 1fr) 18rem;
      gap: 1rem;
    }
    .controls-column {
      padding-left: 0.8rem;
    }
  }
  @media (max-width: 57rem) {
    .preview-controls {
      gap: 0.4rem;
    }
    .preview-controls label {
      gap: 0.25rem;
      font-size: 0.7rem;
    }
    .preview-controls select {
      max-width: 8.3rem;
      font-size: 0.72rem;
    }
  }
  @media (max-height: 44rem) and (min-width: 46rem) {
    .controls-column {
      grid-template-rows: minmax(9rem, 0.6fr) minmax(14rem, 1.4fr);
    }
  }
  @media (max-width: 46rem), (max-height: 35rem) {
    .editor {
      overflow: auto;
      display: flex;
      flex-direction: column;
    }
    .visual-column {
      flex: none;
    }
    .workspace {
      height: 23rem;
      flex: none;
    }
    .controls-column {
      display: flex;
      flex-direction: column;
      flex: none;
      padding: 0;
      border-left: 0;
    }
    .controls-column :global(.manager) {
      height: 16rem;
      flex: none;
    }
    .properties-panel {
      max-height: none;
      min-height: 20rem;
      overflow: visible;
    }
    .properties-scroll {
      overflow: visible;
    }
    .zoom-control {
      margin-left: auto;
    }
  }
</style>
