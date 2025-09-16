<script>
  import { createEventDispatcher } from "svelte";

  export let recorderState = { state: "unknown", loop_running: false };

  const dispatch = createEventDispatcher();

  function send(action) {
    dispatch("action", { action });
  }

  function startMonitor() {
    dispatch("startMonitor");
  }

  function stopMonitor() {
    dispatch("stopMonitor");
  }
</script>

<div class="state-line">
  <span>現在の状態: <strong>{recorderState.state}</strong></span>
  <span>監視タスク: {recorderState.loop_running ? "稼働中" : "停止中"}</span>
</div>
<div class="button-row">
  <button
    on:click={() => send("start")}
    disabled={recorderState.state === "recording" || recorderState.state === "paused"}
  >
    録画開始
  </button>
  <button on:click={() => send("pause")} disabled={recorderState.state !== "recording"}>
    一時停止
  </button>
  <button on:click={() => send("resume")} disabled={recorderState.state !== "paused"}>
    再開
  </button>
  <button on:click={() => send("stop")} disabled={recorderState.state === "stopped"}>
    停止
  </button>
  <button on:click={() => send("cancel")}>
    キャンセル
  </button>
</div>
<div class="button-row">
  <button on:click={startMonitor} disabled={recorderState.loop_running}>
    自動録画監視開始
  </button>
  <button on:click={stopMonitor} disabled={!recorderState.loop_running}>
    自動録画監視停止
  </button>
</div>
