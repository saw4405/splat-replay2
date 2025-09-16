<script>
  import { createEventDispatcher } from "svelte";
  import { formatLength } from "../lib/format.js";

  export let recordedAssets = [];
  export let selectedAsset = null;
  export let metadataForm = {};

  const dispatch = createEventDispatcher();

  function select(asset) {
    dispatch("select", { asset });
  }

  function requestDelete(asset) {
    dispatch("delete", { asset });
  }

  function updateField(key, event) {
    dispatch("updateField", { key, value: event.currentTarget.value });
  }

  function saveMetadata() {
    dispatch("save");
  }

  function closeEditor() {
    dispatch("close");
  }
</script>

<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        <th>ファイル名</th>
        <th>尺</th>
        <th>開始時刻</th>
        <th>結果</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {#if recordedAssets.length === 0}
        <tr>
          <td colspan="5">録画済み動画はありません。</td>
        </tr>
      {:else}
        {#each recordedAssets as asset (asset.asset_id)}
          <tr class:selected={selectedAsset && selectedAsset.asset_id === asset.asset_id}>
            <td>
              <button class="link" on:click={() => select(asset)}>{asset.video_path}</button>
            </td>
            <td>{formatLength(asset.length_seconds)}</td>
            <td>{asset.metadata && asset.metadata.started_at ? asset.metadata.started_at : "-"}</td>
            <td>{asset.metadata && asset.metadata.result ? asset.metadata.result : "-"}</td>
            <td>
              <button on:click={() => requestDelete(asset)}>削除</button>
            </td>
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>

{#if selectedAsset}
  <div class="metadata-editor">
    <h3>メタデータ編集: {selectedAsset.video_path}</h3>
    <div class="metadata-grid">
      {#each Object.keys(metadataForm) as key (key)}
        <label>
          <span>{key}</span>
          <input value={metadataForm[key]} on:input={(event) => updateField(key, event)} />
        </label>
      {/each}
    </div>
    <div class="button-row">
      <button on:click={saveMetadata}>メタデータを保存</button>
      <button on:click={closeEditor}>閉じる</button>
    </div>
  </div>
{/if}
