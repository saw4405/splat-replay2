<script>
  import { createEventDispatcher } from "svelte";
  import { formatLength } from "../lib/format.js";

  export let editedAssets = [];

  const dispatch = createEventDispatcher();

  function requestDelete(asset) {
    dispatch("delete", { asset });
  }
</script>

<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        <th>ファイル名</th>
        <th>尺</th>
        <th>タイトル</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {#if editedAssets.length === 0}
        <tr>
          <td colspan="4">編集済み動画はありません。</td>
        </tr>
      {:else}
        {#each editedAssets as asset (asset.asset_id)}
          <tr>
            <td>{asset.video_path}</td>
            <td>{formatLength(asset.length_seconds)}</td>
            <td>{asset.metadata && asset.metadata.title ? asset.metadata.title : "-"}</td>
            <td>
              <button on:click={() => requestDelete(asset)}>削除</button>
            </td>
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
