<script>
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  function run(path, message) {
    dispatch("run", { path, message });
  }
</script>

<div class="button-row">
  <button on:click={() => run("/workflow/auto", "自動録画+編集+アップロードを開始しました")}>
    一括実行
  </button>
  <button on:click={() => run("/workflow/edit", "自動編集を開始しました")}>
    自動編集
  </button>
  <button on:click={() => run("/workflow/edit/cancel", "自動編集のキャンセルを要求しました")}>
    編集キャンセル
  </button>
  <button on:click={() => run("/workflow/upload", "自動アップロードを開始しました")}>
    自動アップロード
  </button>
  <button on:click={() => run("/workflow/upload/cancel", "自動アップロードのキャンセルを要求しました")}>
    アップロードキャンセル
  </button>
</div>
