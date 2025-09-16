<script>
  import { createEventDispatcher } from "svelte";

  export let behaviorSettings = {
    edit_after_power_off: true,
    sleep_after_upload: false,
  };

  const dispatch = createEventDispatcher();

  function handleToggle(key, event) {
    dispatch("update", { key, value: event.currentTarget.checked });
  }

  function handleSave() {
    dispatch("save");
  }
</script>

<div class="settings">
  <label>
    <input
      type="checkbox"
      checked={behaviorSettings.edit_after_power_off}
      on:change={(event) => handleToggle("edit_after_power_off", event)}
    />
    電源オフ後に自動編集・アップロードを行う
  </label>
  <label>
    <input
      type="checkbox"
      checked={behaviorSettings.sleep_after_upload}
      on:change={(event) => handleToggle("sleep_after_upload", event)}
    />
    アップロード完了後にスリープする
  </label>
  <button on:click={handleSave}>設定を保存</button>
</div>
