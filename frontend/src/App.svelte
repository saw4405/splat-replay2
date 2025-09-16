<script>
  import { onDestroy, onMount } from "svelte";

  import BehaviorSettingsSection from "./components/BehaviorSettingsSection.svelte";
  import EditedAssetsSection from "./components/EditedAssetsSection.svelte";
  import EventLogSection from "./components/EventLogSection.svelte";
  import RecordedAssetsSection from "./components/RecordedAssetsSection.svelte";
  import RecorderControls from "./components/RecorderControls.svelte";
  import StatusBanner from "./components/StatusBanner.svelte";
  import WorkflowActions from "./components/WorkflowActions.svelte";
  import {
    deleteEditedAssetRequest,
    deleteRecordedAssetRequest,
    fetchBehaviorSettings,
    fetchEditedAssets,
    fetchEvents,
    fetchRecordedAssets,
    fetchRecorderState,
    postRecorderAction,
    runWorkflowRequest,
    startMonitorRequest,
    stopMonitorRequest,
    updateBehaviorSettingsRequest,
    updateRecordedMetadata,
  } from "./lib/api.js";

  const MAX_EVENTS = 200;

  let recorderState = { state: "unknown", loop_running: false };
  let events = [];
  let lastEventTs = 0;
  let recordedAssets = [];
  let editedAssets = [];
  let selectedAsset = null;
  let metadataForm = {};
  let behaviorSettings = {
    edit_after_power_off: true,
    sleep_after_upload: false,
  };
  let statusMessage = "";
  let errorMessage = "";
  let pollingTimer;
  let isFetchingEvents = false;

  function setStatus(message) {
    statusMessage = message;
    errorMessage = "";
  }

  function setError(message) {
    errorMessage = message;
    statusMessage = "";
  }

  async function loadRecorderState() {
    try {
      recorderState = await fetchRecorderState();
    } catch (err) {
      setError(`録画状態の取得に失敗しました: ${err.message}`);
    }
  }

  async function sendRecorderAction(action) {
    try {
      await postRecorderAction(action);
      setStatus(`録画コマンド(${action})を送信しました`);
      await loadRecorderState();
    } catch (err) {
      setError(`録画コマンドの送信に失敗しました: ${err.message}`);
    }
  }

  async function startMonitor() {
    try {
      const res = await startMonitorRequest();
      if (res?.status === "already_running") {
        setStatus("自動録画監視は既に動作中です");
      } else {
        setStatus("自動録画監視を開始しました");
      }
      await loadRecorderState();
    } catch (err) {
      setError(`監視タスクの開始に失敗しました: ${err.message}`);
    }
  }

  async function stopMonitor() {
    try {
      const res = await stopMonitorRequest();
      if (res?.status === "stopped") {
        setStatus("監視タスクは既に停止しています");
      } else {
        setStatus("自動録画監視を停止しました");
      }
      await loadRecorderState();
    } catch (err) {
      setError(`監視タスクの停止に失敗しました: ${err.message}`);
    }
  }

  async function runWorkflow(path, message) {
    if (!path) {
      return;
    }
    try {
      await runWorkflowRequest(path);
      setStatus(message ?? "ワークフローを開始しました");
    } catch (err) {
      const baseMessage = message ?? "ワークフロー";
      setError(`${baseMessage}に失敗しました: ${err.message}`);
    }
  }

  async function loadAssets() {
    try {
      const [recorded, edited] = await Promise.all([
        fetchRecordedAssets(),
        fetchEditedAssets(),
      ]);
      recordedAssets = recorded;
      editedAssets = edited;
    } catch (err) {
      setError(`動画一覧の取得に失敗しました: ${err.message}`);
    }
  }

  function selectAsset(asset) {
    selectedAsset = asset;
    if (!asset || !asset.metadata) {
      metadataForm = {};
      return;
    }
    const form = {};
    for (const [key, value] of Object.entries(asset.metadata)) {
      form[key] = value ?? "";
    }
    metadataForm = form;
  }

  function resetSelection() {
    selectedAsset = null;
    metadataForm = {};
  }

  function updateMetadataField(key, value) {
    metadataForm = { ...metadataForm, [key]: value };
  }

  async function saveMetadata() {
    if (!selectedAsset) {
      return;
    }
    try {
      const metadata = {};
      for (const [key, value] of Object.entries(metadataForm)) {
        metadata[key] = value === "" ? null : value;
      }
      await updateRecordedMetadata(selectedAsset.asset_id, metadata);
      setStatus("メタデータを保存しました");
      await loadAssets();
      const updated = recordedAssets.find(
        (asset) => asset.asset_id === selectedAsset.asset_id,
      );
      if (updated) {
        selectAsset(updated);
      } else {
        resetSelection();
      }
    } catch (err) {
      setError(`メタデータの保存に失敗しました: ${err.message}`);
    }
  }

  async function deleteRecordedAsset(asset) {
    if (!asset) {
      return;
    }
    const confirmed = window.confirm(
      `${asset.video_path}\nこの動画を削除しますか？`,
    );
    if (!confirmed) {
      return;
    }
    try {
      await deleteRecordedAssetRequest(asset.asset_id);
      setStatus("録画済み動画を削除しました");
      await loadAssets();
      if (selectedAsset && selectedAsset.asset_id === asset.asset_id) {
        resetSelection();
      }
    } catch (err) {
      setError(`録画済み動画の削除に失敗しました: ${err.message}`);
    }
  }

  async function deleteEditedAsset(asset) {
    if (!asset) {
      return;
    }
    const confirmed = window.confirm(
      `${asset.video_path}\n編集済み動画を削除しますか？`,
    );
    if (!confirmed) {
      return;
    }
    try {
      await deleteEditedAssetRequest(asset.asset_id);
      setStatus("編集済み動画を削除しました");
      await loadAssets();
    } catch (err) {
      setError(`編集済み動画の削除に失敗しました: ${err.message}`);
    }
  }

  async function loadEvents(reset = false) {
    if (isFetchingEvents) {
      return;
    }
    isFetchingEvents = true;
    if (reset) {
      events = [];
      lastEventTs = 0;
    }
    try {
      const after = lastEventTs === 0 ? undefined : lastEventTs;
      const data = await fetchEvents(after);
      if (Array.isArray(data) && data.length > 0) {
        events = [...events, ...data].slice(-MAX_EVENTS);
        lastEventTs = data[data.length - 1].timestamp;
      }
    } catch (err) {
      setError(`イベントの取得に失敗しました: ${err.message}`);
    } finally {
      isFetchingEvents = false;
    }
  }

  async function loadBehavior() {
    try {
      behaviorSettings = await fetchBehaviorSettings();
    } catch (err) {
      setError(`挙動設定の取得に失敗しました: ${err.message}`);
    }
  }

  function updateBehaviorSetting(key, value) {
    behaviorSettings = { ...behaviorSettings, [key]: value };
  }

  async function saveBehavior() {
    try {
      const saved = await updateBehaviorSettingsRequest(behaviorSettings);
      behaviorSettings = saved;
      setStatus("挙動設定を保存しました");
    } catch (err) {
      setError(`挙動設定の保存に失敗しました: ${err.message}`);
    }
  }

  async function refreshAll() {
    await Promise.all([
      loadRecorderState(),
      loadAssets(),
      loadBehavior(),
      loadEvents(true),
    ]);
  }

  onMount(() => {
    void refreshAll();
    pollingTimer = setInterval(() => {
      void loadEvents();
    }, 2000);
  });

  onDestroy(() => {
    if (pollingTimer) {
      clearInterval(pollingTimer);
    }
  });

  function handleRecorderAction(event) {
    const { action } = event.detail ?? {};
    if (action) {
      void sendRecorderAction(action);
    }
  }

  function handleRunWorkflow(event) {
    const { path, message } = event.detail ?? {};
    void runWorkflow(path, message);
  }

  function handleBehaviorUpdate(event) {
    const { key, value } = event.detail ?? {};
    if (typeof key === "string") {
      updateBehaviorSetting(key, value);
    }
  }

  function handleMetadataUpdate(event) {
    const { key, value } = event.detail ?? {};
    if (typeof key === "string") {
      updateMetadataField(key, value ?? "");
    }
  }
</script>

<main>
  <h1>Splat Replay コントロールパネル</h1>

  <StatusBanner {statusMessage} {errorMessage} />

  <section class="section-card">
    <h2>録画制御</h2>
    <RecorderControls
      {recorderState}
      on:action={handleRecorderAction}
      on:startMonitor={() => void startMonitor()}
      on:stopMonitor={() => void stopMonitor()}
    />
  </section>

  <section class="section-card">
    <h2>自動処理</h2>
    <WorkflowActions on:run={handleRunWorkflow} />
  </section>

  <section class="section-card">
    <h2>挙動設定</h2>
    <BehaviorSettingsSection
      {behaviorSettings}
      on:update={handleBehaviorUpdate}
      on:save={() => void saveBehavior()}
    />
  </section>

  <section class="section-card">
    <h2>イベントログ</h2>
    <EventLogSection {events} on:refresh={() => void loadEvents()} />
  </section>

  <section class="section-card">
    <h2>録画済み動画</h2>
    <RecordedAssetsSection
      {recordedAssets}
      {selectedAsset}
      {metadataForm}
      on:select={(event) => selectAsset(event.detail?.asset ?? null)}
      on:delete={(event) => void deleteRecordedAsset(event.detail?.asset ?? null)}
      on:updateField={handleMetadataUpdate}
      on:save={() => void saveMetadata()}
      on:close={() => resetSelection()}
    />
  </section>

  <section class="section-card">
    <h2>編集済み動画</h2>
    <EditedAssetsSection
      {editedAssets}
      on:delete={(event) => void deleteEditedAsset(event.detail?.asset ?? null)}
    />
  </section>
</main>
