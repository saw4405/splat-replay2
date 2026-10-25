<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { Check, LoaderCircle, Scissors, X } from 'lucide-svelte';
  import ImportedCandidateReview from './ImportedCandidateReview.svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import SubtitleEditorDialog from '../metadata/SubtitleEditorDialog.svelte';
  import type { ImportedBattle, ImportedVideoJob } from '../../api/importedVideos';
  import { getMetadataOptions } from '../../api/metadata';
  import type { MetadataOptions } from '../../api/types';
  import type { SubtitleData } from '../../api/types';
  import {
    cancelImportedJob,
    getImportedVideo,
    getImportedCandidateSubtitle,
    importedAssetUrl,
    listImportedVideos,
    retryImportedScan,
    startImportedEdit,
    updateImportedCandidate,
    updateImportedCandidateSubtitle,
    updateImportedSelection,
    updateImportedOutput,
    updateImportedSourceTime,
    uploadImportedVideo,
  } from '../../api/importedVideos';

  interface Props {
    open?: boolean;
    file?: File | null;
    onChooseFile?: () => void;
  }

  let { open = $bindable(false), file = null, onChooseFile }: Props = $props();
  let candidatePatch = $state<Record<string, string | number | string[] | null>>({});
  let candidateSaving = $state(false);
  let previewMode = $state<'quality' | 'video'>('quality');
  let metadataOptions = $state<MetadataOptions | null>(null);
  let sourceTimeDraft = $state('');
  let outputSaving = $state(false);
  let notice = $state('');
  let transitionBusy = $state(false);
  let reviewHeading = $state<HTMLHeadingElement>();
  let workflowElement = $state<HTMLDivElement>();
  $effect(() => {
    if (!open || step !== 2 || panelIndex < 0 || !selectedCandidateId) return;
    void tick().then(() => {
      if (workflowElement) workflowElement.scrollTop = 0;
      reviewHeading?.focus({ preventScroll: true });
    });
  });
  let selectedCandidateId = $state('');
  let selectedOutputId = $state('');
  let step = $state<1 | 2 | 3 | 4>(1);
  let panelIndex = $state(0);
  const panels = ['match_select', 'weapons', 'result_full', 'judgement'] as const;
  let jobs = $state<ImportedVideoJob[]>([]);
  let activeJob = $state<ImportedVideoJob | null>(null);
  let reviewCandidates = $derived(
    activeJob?.candidates.filter((item) => item.selected && item.clip_ready) ?? []
  );

  let uploading = $state(false);
  let uploadPercent = $state(0);
  let sourceName = $state('');
  let titleDraft = $state('');
  let descriptionDraft = $state('');
  let errorMessage = $state('');
  let selectionSaving = $state(false);
  let uploadController: AbortController | null = null;
  let subtitleDialogOpen = $state(false);
  let subtitleJobId = $state('');
  let subtitleCandidateId = $state('');
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let lastOpened = false;
  let consumedFile: File | null = null;
  let selectedCount = $derived(
    activeJob?.candidates.filter((item) => item.selected && item.clip_ready).length ?? 0
  );
  let focusedCandidate = $derived(
    activeJob?.candidates.find((item) => item.id === selectedCandidateId) ??
      activeJob?.candidates[0] ??
      null
  );
  let outputs = $derived(
    activeJob?.outputs ??
      (activeJob?.output_id
        ? [
            {
              id: activeJob.output_id,
              title: activeJob.title,
              description: activeJob.description,
              candidate_ids: activeJob.candidates
                .filter((item) => item.selected)
                .map((item) => item.id),
              has_thumbnail: activeJob.has_thumbnail,
              has_subtitle: activeJob.has_subtitle,
            },
          ]
        : [])
  );
  let focusedOutput = $derived(
    outputs.find((item) => item.id === selectedOutputId) ?? outputs[0] ?? null
  );
  let subtitleCandidate = $derived(
    activeJob?.id === subtitleJobId
      ? (activeJob.candidates.find((item) => item.id === subtitleCandidateId) ?? null)
      : null
  );

  $effect(() => {
    titleDraft = focusedOutput?.title ?? '';
    descriptionDraft = focusedOutput?.description ?? '';
  });

  $effect(() => {
    if (open && !lastOpened) void loadJobs();
    lastOpened = open;
  });

  $effect(() => {
    if (open && file && file !== consumedFile) {
      consumedFile = file;
      void importFile(file);
    }
  });

  async function loadJobs(): Promise<void> {
    try {
      jobs = await listImportedVideos();
      if (activeJob) {
        activeJob = jobs.find((job) => job.id === activeJob?.id) ?? activeJob;
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '取込履歴を読み込めませんでした';
    }
  }

  async function importFile(selectedFile: File): Promise<void> {
    clearTimeout(pollTimer);
    activeJob = null;
    step = 1;
    panelIndex = 0;
    candidatePatch = {};
    previewMode = 'quality';
    notice = '';
    sourceName = selectedFile.name;
    titleDraft = '';
    descriptionDraft = '';
    errorMessage = '';
    uploading = true;
    uploadPercent = 0;
    const controller = new AbortController();
    uploadController = controller;
    try {
      activeJob = await uploadImportedVideo(
        selectedFile,
        (percent) => {
          uploadPercent = percent;
        },
        controller.signal
      );
      sourceTimeDraft = activeJob.source_started_at?.slice(0, 19) ?? '';
      await loadJobs();
      schedulePoll();
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '動画を取り込めませんでした';
    } finally {
      uploading = false;
      if (uploadController === controller) uploadController = null;
    }
  }

  function schedulePoll(): void {
    clearTimeout(pollTimer);
    const jobId = activeJob?.id;
    if (!jobId || !activeJob || !['scanning', 'editing'].includes(activeJob.state)) return;
    pollTimer = setTimeout(() => void pollJob(jobId), 900);
  }

  async function pollJob(jobId: string): Promise<void> {
    try {
      const job = await getImportedVideo(jobId);
      if (activeJob?.id === jobId) {
        if (activeJob.state === 'editing' && job.state === 'completed' && job.output_id) {
          selectedOutputId = job.output_id;
          step = 4;
        }
        activeJob = job;
      }
      jobs = jobs.map((item) => (item.id === jobId ? job : item));
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '処理状況を取得できませんでした';
    }
    schedulePoll();
  }

  function openSavedJob(job: ImportedVideoJob): void {
    activeJob = job;
    selectedCandidateId = '';
    selectedOutputId = job.output_id ?? '';
    step = job.state === 'completed' ? 4 : job.state === 'editing' ? 3 : 1;
    panelIndex = 0;
    candidatePatch = {};
    previewMode = 'quality';
    notice = '';
    sourceTimeDraft = job.source_started_at?.slice(0, 19) ?? '';
    titleDraft = job.title ?? '';
    descriptionDraft = job.description ?? '';
    errorMessage = '';
    schedulePoll();
  }

  function selectedIds(candidates: ImportedBattle[]): string[] {
    return candidates
      .filter((candidate) => candidate.selected && candidate.clip_ready)
      .map((candidate) => candidate.id);
  }

  async function persistSelection(candidates: ImportedBattle[]): Promise<void> {
    if (!activeJob || selectionSaving) return;
    const previousJob = activeJob;
    activeJob = { ...previousJob, candidates };
    selectionSaving = true;
    try {
      const updatedJob = await updateImportedSelection(previousJob.id, selectedIds(candidates));
      if (activeJob?.id === previousJob.id) activeJob = updatedJob;
      jobs = jobs.map((item) => (item.id === previousJob.id ? updatedJob : item));
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '選択を保存できませんでした';
      try {
        const savedJob = await getImportedVideo(previousJob.id);
        if (activeJob?.id === previousJob.id) activeJob = savedJob;
        jobs = jobs.map((item) => (item.id === previousJob.id ? savedJob : item));
      } catch {
        if (activeJob?.id === previousJob.id) activeJob = previousJob;
      }
    } finally {
      selectionSaving = false;
    }
  }

  async function changeSelection(candidateId: string, selected: boolean): Promise<void> {
    if (!activeJob || selectionSaving) return;
    const candidates = activeJob.candidates.map((item) =>
      item.id === candidateId ? { ...item, selected } : item
    );
    await persistSelection(candidates);
  }

  async function selectAll(selected: boolean): Promise<void> {
    if (!activeJob || selectionSaving) return;
    const candidates = activeJob.candidates.map((item) => ({ ...item, selected }));
    await persistSelection(candidates);
  }

  async function saveOutputMetadata(): Promise<boolean> {
    if (outputSaving) return false;
    if (!activeJob || !focusedOutput) return true;
    if (
      titleDraft === (focusedOutput.title ?? '') &&
      descriptionDraft === (focusedOutput.description ?? '')
    )
      return true;
    outputSaving = true;
    try {
      activeJob = await updateImportedOutput(
        activeJob.id,
        focusedOutput.id,
        titleDraft,
        descriptionDraft
      );
      errorMessage = '';
      notice = 'タイトル・説明を保存しました';
      return true;
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '編集結果を保存できませんでした';
      return false;
    } finally {
      outputSaving = false;
    }
  }

  async function savePendingCandidate(): Promise<boolean> {
    if (!Object.keys(candidatePatch).length) return true;
    if (!activeJob || !focusedCandidate || candidateSaving) return false;
    for (const key of ['kill', 'death', 'special', 'gold_medals', 'silver_medals']) {
      if (key in candidatePatch && candidatePatch[key] === null) {
        errorMessage = '数値を入力してください（0可）。未取得の項目は空欄のままにできます。';
        return false;
      }
    }
    for (const key of ['kill', 'death', 'special', 'gold_medals', 'silver_medals']) {
      const value = candidatePatch[key];
      if (
        typeof value === 'number' &&
        (!Number.isInteger(value) ||
          value < 0 ||
          ((key === 'gold_medals' || key === 'silver_medals') && value > 3))
      ) {
        errorMessage = '回数は0以上の整数、表彰数は0〜3で入力してください。';
        return false;
      }
    }
    const gold = candidatePatch.gold_medals ?? focusedCandidate.metadata.gold_medals ?? 0;
    const silver = candidatePatch.silver_medals ?? focusedCandidate.metadata.silver_medals ?? 0;
    if (typeof gold === 'number' && typeof silver === 'number' && gold + silver > 3) {
      errorMessage = '金表彰と銀表彰の合計は3以下で入力してください。';
      return false;
    }
    candidateSaving = true;
    try {
      activeJob = await updateImportedCandidate(activeJob.id, focusedCandidate.id, candidatePatch);
      candidatePatch = {};
      errorMessage = '';
      return true;
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '修正を保存できませんでした';
      return false;
    } finally {
      candidateSaving = false;
    }
  }

  async function closeReview(): Promise<void> {
    if ((await savePendingCandidate()) && (await saveOutputMetadata())) open = false;
  }

  async function transition(action: () => Promise<void>): Promise<void> {
    if (transitionBusy) return;
    transitionBusy = true;
    try {
      await action();
    } finally {
      transitionBusy = false;
    }
  }

  async function beginReview(): Promise<void> {
    if (!activeJob || !selectedCount || selectionSaving) return;
    if (
      sourceTimeDraft &&
      (activeJob.source_started_at_inferred ||
        sourceTimeDraft !== activeJob.source_started_at?.slice(0, 19))
    ) {
      try {
        activeJob = await updateImportedSourceTime(activeJob.id, sourceTimeDraft);
      } catch (error) {
        errorMessage =
          error instanceof Error ? error.message : '録画開始日時を保存できませんでした';
        return;
      }
    }
    errorMessage = '';
    selectedCandidateId = reviewCandidates[0]?.id ?? '';
    panelIndex = 0;
    previewMode = 'quality';
    step = 2;
  }

  async function moveReview(direction: -1 | 1): Promise<void> {
    if (!(await savePendingCandidate())) return;
    previewMode = 'quality';
    const index = reviewCandidates.findIndex((item) => item.id === focusedCandidate?.id);
    if (direction === 1) {
      if (panelIndex < panels.length - 1) panelIndex += 1;
      else if (index < reviewCandidates.length - 1) {
        selectedCandidateId = reviewCandidates[index + 1].id;
        panelIndex = 0;
      } else step = 3;
    } else if (panelIndex > 0) panelIndex -= 1;
    else if (index > 0) {
      selectedCandidateId = reviewCandidates[index - 1].id;
      panelIndex = panels.length - 1;
    } else step = 1;
  }

  async function runEdit(): Promise<void> {
    if (!(await savePendingCandidate())) return;
    if (!activeJob || selectedCount === 0 || selectionSaving) return;
    errorMessage = '';
    try {
      activeJob = await startImportedEdit(activeJob.id);
      if (activeJob.state === 'completed' && activeJob.output_id) {
        selectedOutputId = activeJob.output_id;
      }
      step = activeJob.state === 'completed' ? 4 : 3;
      schedulePoll();
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '編集を開始できませんでした';
    }
  }

  async function cancelCurrent(): Promise<void> {
    if (uploading) {
      uploadController?.abort();
      return;
    }
    if (!activeJob) return;
    try {
      activeJob = await cancelImportedJob(activeJob.id);
      clearTimeout(pollTimer);
      await loadJobs();
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '処理を中止できませんでした';
    }
  }

  async function retryScan(): Promise<void> {
    if (!activeJob) return;
    errorMessage = '';
    try {
      activeJob = await retryImportedScan(activeJob.id);
      schedulePoll();
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : '再解析を開始できませんでした';
    }
  }

  function openSubtitleEditor(candidate: ImportedBattle): void {
    if (!activeJob) return;
    subtitleJobId = activeJob.id;
    subtitleCandidateId = candidate.id;
    subtitleDialogOpen = true;
  }

  function loadCandidateSubtitle(candidateId: string): Promise<SubtitleData> {
    return getImportedCandidateSubtitle(subtitleJobId, candidateId);
  }

  function saveCandidateSubtitle(candidateId: string, data: SubtitleData): Promise<SubtitleData> {
    return updateImportedCandidateSubtitle(subtitleJobId, candidateId, data);
  }

  function candidateSubtitleSaved(data: SubtitleData): void {
    if (!activeJob || activeJob.id !== subtitleJobId) return;
    const hasSubtitle = data.blocks.length > 0;
    activeJob = {
      ...activeJob,
      candidates: activeJob.candidates.map((candidate) =>
        candidate.id === subtitleCandidateId
          ? { ...candidate, has_subtitle: hasSubtitle }
          : candidate
      ),
    };
    jobs = jobs.map((job) => (job.id === activeJob?.id ? activeJob! : job));
  }

  function stateLabel(state: ImportedVideoJob['state']): string {
    return {
      queued: '待機中',
      scanning: '対戦を解析中',
      ready: '編集できます',
      editing: '動画を編集・保存中',
      completed: '編集済み',
      failed: '確認が必要です',
      cancelled: '中止しました',
    }[state];
  }

  function formatTime(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remainder = (seconds % 60).toFixed(1).padStart(4, '0');
    return `${minutes}:${remainder}`;
  }

  onMount(() => {
    void getMetadataOptions()
      .then((options) => {
        metadataOptions = options;
      })
      .catch((error: unknown) => {
        errorMessage = error instanceof Error ? error.message : '項目名を読み込めませんでした';
      });
  });

  function metadataLabel(
    kind: 'rules' | 'stages' | 'judgements',
    value: ImportedBattle['metadata'][string] | undefined
  ): string {
    return (
      metadataOptions?.[kind]?.find((option) => option.key === value)?.label ??
      displayMetadata(value)
    );
  }

  function displayMetadata(value: ImportedBattle['metadata'][string] | undefined): string {
    return typeof value === 'string' && value ? value.replaceAll('_', ' ') : '未取得';
  }

  onDestroy(() => {
    clearTimeout(pollTimer);
    uploadController?.abort();
  });
</script>

<BaseDialog
  bind:open
  onClose={closeReview}
  title="動画を取り込んで編集"
  showFooter={Boolean(activeJob?.candidates.length)}
  footerVariant="custom"
  showCloseButton={true}
  maxWidth="78rem"
  maxHeight="92vh"
  minHeight="min(48rem, 88vh)"
  mobileFullscreen={true}
>
  <div bind:this={workflowElement} class="workflow import-review-workflow">
    {#if errorMessage}
      <p class="error-message" role="alert">{errorMessage}</p>
    {/if}

    {#if notice}<p class="muted" role="status">{notice}</p>{/if}
    {#if uploading}
      <section class="upload-state" aria-live="polite">
        <LoaderCircle class="spinner" size={24} aria-hidden="true" />
        <div>
          <strong>{sourceName} を取り込んでいます</strong>
          <progress max="100" value={uploadPercent} aria-label="動画の送信進捗"></progress>
          <span>{Math.round(uploadPercent)}%</span>
        </div>
        <button class="quiet-button cancel-button" type="button" onclick={cancelCurrent}>
          <X size={15} aria-hidden="true" /> 取込を中止
        </button>
      </section>
    {/if}

    {#if activeJob}
      <header class="job-header">
        <div class="job-summary">
          <h2 title={activeJob.source_name}>{activeJob.source_name}</h2>
          {#if ['queued', 'scanning', 'editing', 'failed', 'cancelled'].includes(activeJob.state)}<p
              class="job-status"
              role="status"
            >
              {stateLabel(activeJob.state)}
            </p>{/if}
        </div>
        {#if activeJob.candidates.length > 0}
          <ol class="wizard-progress" aria-label="編集の手順">
            {#each ['対象を選ぶ', '内容を確認', '編集・保存', '完了'] as label, index}
              <li
                aria-current={step === index + 1 ? 'step' : undefined}
                class:current={step === index + 1}
                class:complete={step > index + 1}
              >
                <span class="step-number" aria-hidden="true"
                  >{#if step > index + 1}<Check size={14} />{:else}{index + 1}{/if}</span
                ><span>{label}</span>
              </li>
            {/each}
          </ol>
        {/if}
        {#if step === 1 && onChooseFile}
          <button
            class="quiet-button"
            type="button"
            onclick={onChooseFile}
            disabled={!onChooseFile}
          >
            別の動画を選ぶ
          </button>{/if}
      </header>
      {#if ['queued', 'scanning', 'editing'].includes(activeJob.state)}
        <div class="job-progress">
          <progress max="100" value={activeJob.progress_percent} aria-label="動画の解析・編集進捗"
          ></progress>
          <span>{Math.round(activeJob.progress_percent)}%</span>
          <button class="quiet-button cancel-button" type="button" onclick={cancelCurrent}>
            <X size={15} aria-hidden="true" /> 中止
          </button>
        </div>
      {/if}
      {#if activeJob.error}
        <p class="job-notice" role="status">{activeJob.error}</p>
      {/if}

      {#if activeJob.candidates.length > 0}
        {#if step === 1}
          <h3>編集するバトルを選んでください</h3>
          <div class="source-time">
            <label
              >元動画の録画開始日時 <input
                type="datetime-local"
                step="1"
                bind:value={sourceTimeDraft}
                disabled={['scanning', 'editing'].includes(activeJob.state)}
              /></label
            >
            <small
              >{activeJob.source_started_at_inferred
                ? 'ファイル名からの推定です。確認して訂正してください。'
                : activeJob.source_started_at
                  ? '各バトルの日時に反映します。'
                  : '日時が未設定です。入力すると各バトルに反映します。'}</small
            >
          </div>
          <section class="review-list" aria-label="バトル一覧">
            <div class="selection-actions">
              <button
                class="text-button"
                disabled={selectionSaving || ['scanning', 'editing'].includes(activeJob.state)}
                onclick={() => void selectAll(true)}>すべて選択</button
              >
              <button
                class="text-button"
                disabled={selectionSaving || ['scanning', 'editing'].includes(activeJob.state)}
                onclick={() => void selectAll(false)}>すべて解除</button
              >
            </div>
            {#each activeJob.candidates as candidate, index (candidate.id)}
              <label class="list-row">
                <input
                  type="checkbox"
                  aria-label={`${index + 1}番目のバトルを編集に含める`}
                  checked={candidate.selected}
                  disabled={!candidate.clip_ready ||
                    selectionSaving ||
                    ['scanning', 'editing'].includes(activeJob.state)}
                  onchange={(event) =>
                    void changeSelection(candidate.id, event.currentTarget.checked)}
                />
                <span class="candidate-button"
                  ><strong>バトル {index + 1}</strong><span
                    >{metadataLabel('rules', candidate.metadata.rule)} / {metadataLabel(
                      'stages',
                      candidate.metadata.stage
                    )}</span
                  ><small
                    >{formatTime(candidate.start_seconds)}–{formatTime(candidate.end_seconds)} · {metadataLabel(
                      'judgements',
                      candidate.metadata.judgement
                    )}</small
                  ></span
                >
              </label>
            {/each}
          </section>
        {:else if step === 2 && focusedCandidate}
          <section class="review-detail" aria-label="選択したバトルの詳細">
            {#if step === 2 && focusedCandidate}
              <div class="battle-context">
                <h3 bind:this={reviewHeading} tabindex="-1">
                  バトル {activeJob.candidates.findIndex(
                    (item) => item.id === focusedCandidate.id
                  ) + 1} の確認
                </h3>
                <small
                  >画像 {panelIndex + 1} / {panels.length} · バトル {reviewCandidates.findIndex(
                    (item) => item.id === focusedCandidate.id
                  ) + 1} / {reviewCandidates.length}</small
                >
              </div>
            {/if}

            {#if previewMode === 'quality'}
              <ImportedCandidateReview
                jobId={activeJob.id}
                candidate={focusedCandidate}
                options={metadataOptions}
                patch={candidatePatch}
                displayedPanel={panels[panelIndex]}
                disabled={candidateSaving || transitionBusy}
                onChange={(key, value) => (candidatePatch = { ...candidatePatch, [key]: value })}
              />
            {:else}
              <video
                class="review-video"
                controls
                preload="metadata"
                src={importedAssetUrl(activeJob.id, `candidate/${focusedCandidate.id}/video.mp4`)}
                aria-label="選択したバトルのプレビュー"><track kind="captions" /></video
              >
            {/if}
            <details>
              <summary>動画・字幕を確認</summary>
              <button
                class="quiet-button"
                onclick={() => (previewMode = previewMode === 'quality' ? 'video' : 'quality')}
                >{previewMode === 'quality' ? '動画を確認' : '認識結果へ戻る'}</button
              >
              <button class="quiet-button" onclick={() => openSubtitleEditor(focusedCandidate!)}
                >字幕を編集</button
              >
            </details>
          </section>
        {:else if step === 3}
          <section class="empty-result">
            <h3>
              {activeJob.state === 'editing'
                ? '動画を編集・保存しています'
                : '確認したバトルを編集・保存します'}
            </h3>
            <p>{selectedCount}件を選択 · 日付・時間帯ごとに編集します。</p>
            <p class="muted">編集結果はこの端末に自動で保存します。</p>
          </section>
        {:else if step === 4}
          <div class="saved-output-summary">
            <div>
              <h3>編集結果を保存しました</h3>
              {#if activeJob.output_directory}<p class="muted">
                  保存先: {activeJob.output_directory}
                </p>{/if}
            </div>
            {#if activeJob.output_directory}
              <button
                class="quiet-button"
                onclick={async () => {
                  try {
                    await navigator.clipboard.writeText(activeJob!.output_directory!);
                    notice = '保存先をコピーしました';
                  } catch {
                    errorMessage = '保存先をコピーできませんでした';
                  }
                }}>保存先をコピー</button
              >
            {/if}
          </div>
          {#if outputs.length > 1}
            <label class="output-selection">
              <span>編集結果</span>
              <select
                aria-label="編集結果"
                value={focusedOutput?.id ?? ''}
                disabled={outputSaving}
                onchange={async (event) => {
                  const select = event.currentTarget;
                  const outputId = select.value;
                  select.value = focusedOutput?.id ?? '';
                  if (await saveOutputMetadata()) selectedOutputId = outputId;
                }}
              >
                {#each outputs as output, index (output.id)}
                  <option value={output.id}
                    >{index + 1}. {output.title ?? '編集結果'} · {output.candidate_ids
                      .length}バトル</option
                  >
                {/each}
              </select>
              <small
                >{outputs.findIndex((output) => output.id === focusedOutput?.id) + 1} / {outputs.length}</small
              >
            </label>
          {/if}
          {#if focusedOutput}
            <div class="output-media">
              <video
                class="review-video"
                controls
                preload="metadata"
                src={importedAssetUrl(activeJob.id, `output/${focusedOutput.id}/video.mp4`)}
                aria-label="編集済み動画のプレビュー"><track kind="captions" /></video
              >
              {#if focusedOutput.has_thumbnail}<img
                  class="output-thumbnail"
                  src={importedAssetUrl(activeJob.id, `output/${focusedOutput.id}/thumbnail.png`)}
                  alt="編集結果のサムネイル"
                />{/if}
            </div>
            <section class="output-details" aria-label="編集結果の情報">
              <label><span>タイトル</span><input bind:value={titleDraft} maxlength="200" /></label>
              <label
                ><span>説明</span><textarea bind:value={descriptionDraft} rows="3"
                ></textarea></label
              >
              <button class="quiet-button" disabled={outputSaving} onclick={saveOutputMetadata}
                >タイトル・説明を保存</button
              >
            </section>
          {/if}
        {/if}
      {:else if activeJob.state === 'failed' && !uploading}
        <div class="empty-result">
          <p>バトル候補を作成できませんでした。</p>
          <button class="quiet-button" type="button" onclick={retryScan}>もう一度解析</button>
        </div>
      {:else if activeJob.state === 'queued'}
        <div class="empty-result">
          <p>前回の解析は中断しています。保存済みの候補を再確認するか、解析を再開できます。</p>
          <button class="quiet-button" type="button" onclick={retryScan}>解析を再開</button>
        </div>
      {:else if activeJob.state === 'scanning'}
        <div class="empty-result">
          <LoaderCircle class="spinner" size={26} aria-hidden="true" />
          <p>動画を順に確認しています。長い動画は完了まで時間がかかることがあります。</p>
        </div>
      {/if}
    {:else if !uploading}
      <section class="import-start">
        <div class="film-mark"><Check size={24} aria-hidden="true" /></div>
        <h2>編集する動画を選んでください</h2>
        <p>動画はこの端末内で解析・編集します。元動画は変更せず、投稿もしません。</p>
        <button class="primary-button" type="button" onclick={onChooseFile} disabled={!onChooseFile}
          >動画を選択</button
        >
      </section>
    {/if}

    {#if jobs.length > 0 && !activeJob}
      <section class="saved-jobs">
        <h3>取り込み済み動画</h3>
        {#each jobs as job (job.id)}
          <button class="saved-job" type="button" onclick={() => openSavedJob(job)}>
            <span>{job.source_name}</span>
            <small>{stateLabel(job.state)} · {job.candidates.length}件</small>
          </button>
        {/each}
      </section>
    {/if}
  </div>
  {#snippet footer()}
    {#if activeJob}
      <div class="edit-actions">
        {#if step === 2}
          <button
            class="quiet-button"
            disabled={candidateSaving || transitionBusy}
            onclick={() => void transition(() => moveReview(-1))}>戻る</button
          >
        {:else if step === 3 && activeJob.state !== 'editing'}
          <button
            class="quiet-button"
            onclick={() => {
              panelIndex = panels.length - 1;
              step = 2;
            }}>戻る</button
          >
        {:else if step === 4}
          <button
            class="quiet-button"
            onclick={async () => {
              if (await saveOutputMetadata()) step = 3;
            }}>戻る</button
          >
        {:else}<span class="muted">{selectedCount}件を選択</span>{/if}
        {#if step === 1}
          <button
            class="primary-button"
            disabled={transitionBusy ||
              selectionSaving ||
              selectedCount === 0 ||
              ['queued', 'scanning', 'editing'].includes(activeJob.state)}
            onclick={() => void transition(beginReview)}>内容を確認する</button
          >
        {:else if step === 2}
          <button
            class="primary-button"
            disabled={candidateSaving || transitionBusy}
            onclick={() => void transition(() => moveReview(1))}
            >{candidateSaving
              ? '保存中'
              : panelIndex === panels.length - 1 &&
                  focusedCandidate?.id === reviewCandidates.at(-1)?.id
                ? '確認を終える'
                : '確認して次へ'}</button
          >
        {:else if step === 3}
          <button
            class="primary-button"
            disabled={transitionBusy ||
              activeJob.state === 'editing' ||
              selectionSaving ||
              selectedCount === 0}
            onclick={() => void transition(runEdit)}
            >{#if activeJob.state === 'editing'}<LoaderCircle
                class="spinner"
                size={17}
                aria-hidden="true"
              />保存中{:else}<Scissors size={17} aria-hidden="true" />編集・保存する{/if}</button
          >
        {:else}
          <button class="primary-button" onclick={closeReview}>完了</button>
        {/if}
      </div>
    {/if}
  {/snippet}
</BaseDialog>

{#if subtitleCandidate}
  <SubtitleEditorDialog
    bind:visible={subtitleDialogOpen}
    videoId={subtitleCandidateId}
    videoUrl={importedAssetUrl(subtitleJobId, `candidate/${subtitleCandidateId}/video.mp4`)}
    loadSubtitle={loadCandidateSubtitle}
    saveSubtitle={saveCandidateSubtitle}
    onSaved={candidateSubtitleSaved}
    saveNotice="候補字幕を保存します。編集済み動画へ反映するには、選択した候補をもう一度編集してください。"
  />
{/if}

<style>
  :global(.dialog-container:has(> .dialog-body > .import-review-workflow) > .dialog-header) {
    padding: 0.75rem 1rem;
  }
  :global(.dialog-container:has(> .dialog-body > .import-review-workflow) > .dialog-header h2) {
    font-size: 1.25rem;
  }
  :global(.dialog-body:has(> .import-review-workflow)) {
    padding: 1rem;
  }

  :global(.dialog-container:has(> .dialog-body > .import-review-workflow)) {
    height: min(48rem, 88vh);
  }
  :global(.dialog-container:has(> .dialog-body > .import-review-workflow) > .dialog-footer) {
    padding: 0.75rem 1rem;
  }
  .wizard-progress {
    flex: 1 1 25rem;
    display: flex;
    gap: 0;
    list-style: none;
    padding: 0.25rem 0;
    margin: 0;
    font-size: 0.8rem;
    color: var(--theme-color-text-secondary);
  }
  .wizard-progress li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex: 1;
  }
  .wizard-progress li:not(:last-child)::after {
    content: '';
    height: 1px;
    background: var(--glass-border);
    flex: 1;
    margin: 0 0.6rem;
  }
  .step-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.65rem;
    height: 1.65rem;
    flex-shrink: 0;
    border: 1px solid var(--glass-border);
    border-radius: 50%;
  }
  .wizard-progress .current {
    color: var(--theme-accent-color);
    font-weight: 700;
  }
  .current .step-number {
    border-color: var(--theme-accent-color);
    background: rgba(var(--theme-rgb-accent), 0.15);
  }
  .complete .step-number {
    color: var(--theme-accent-color);
    background: rgba(var(--theme-rgb-accent), 0.08);
  }
  .battle-context {
    justify-content: space-between;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .battle-context h3 {
    font-size: 0.9rem;
  }
  .saved-output-summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }
  .saved-output-summary > div {
    min-width: 0;
  }
  .saved-output-summary button {
    flex-shrink: 0;
  }
  .output-selection {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.85rem;
  }
  .output-selection select {
    flex: 1;
    min-width: 0;
    padding: 0.4rem;
    border: 1px solid var(--glass-border);
    border-radius: 0.5rem;
    background: rgb(var(--theme-rgb-surface-card));
    color: inherit;
    font: inherit;
  }
  .output-media {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 1rem;
  }
  .output-media .review-video,
  .output-thumbnail {
    height: min(24vh, 12rem);
    width: 100%;
    object-fit: contain;
  }
  .workflow {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    text-align: left;
    min-height: 0;
    flex: 1;
    overflow: auto;
    color: var(--theme-color-text-primary);
  }
  .workflow > * {
    flex-shrink: 0;
  }
  .source-time,
  .job-header,
  .job-progress,
  .edit-actions,
  .selection-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .job-header {
    justify-content: space-between;
  }
  h2,
  h3,
  p {
    margin: 0;
  }
  h2 {
    font-size: 1.1rem;
    overflow-wrap: anywhere;
  }
  h3 {
    font-size: 1rem;
  }
  .muted {
    overflow-wrap: anywhere;
  }
  .job-status,
  .muted,
  small {
    color: var(--theme-color-text-secondary);
    font-size: 0.8rem;
  }
  .job-header {
    flex-shrink: 0;
    gap: 0.5rem;
  }
  .job-summary {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    column-gap: 1rem;
    row-gap: 0.25rem;
    min-width: 0;
    flex: 0 1 15rem;
  }
  .job-summary h2 {
    font-size: 0.8rem;
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .source-time {
    gap: 0.5rem;
    flex-shrink: 0;
  }
  .source-time label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
  }
  .source-time input {
    width: 13rem;
    min-height: 2rem;
    padding: 0.25rem 0.5rem;
    margin: 0;
    color: inherit;
    font: inherit;
    border: 1px solid var(--glass-border);
    border-radius: 0.5rem;
    background: rgba(var(--theme-rgb-black), 0.2);
  }
  .source-time small {
    font-size: 0.75rem;
  }

  .job-progress progress {
    flex: 1;
  }
  progress {
    accent-color: var(--theme-accent-color);
    width: 100%;
  }
  .review-list,
  .review-detail {
    overflow: visible;
    min-height: 0;
    padding: 0.25rem 0.5rem 0.5rem 0.25rem;
  }
  .review-detail {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .list-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border: 1px solid var(--glass-border);
    border-radius: 0.75rem;
    margin-bottom: 0.5rem;
    padding: 0.5rem;
    background: rgba(var(--theme-rgb-surface-card), 0.6);
  }
  .candidate-button {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    text-align: left;
    border: 0;
    background: transparent;
    color: inherit;
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
    cursor: pointer;
    padding: 0.25rem;
  }
  .candidate-button span {
    font-size: 0.8rem;
  }
  input[type='checkbox'] {
    accent-color: var(--theme-accent-color);
  }
  .review-video {
    display: block;
    flex-shrink: 0;
    width: 100%;
    height: min(27vh, 16rem);
    object-fit: contain;
    border-radius: 0.5rem;
    background: rgba(var(--theme-rgb-black), 0.7);
  }
  .text-button {
    color: var(--theme-accent-color);
  }
  .text-button {
    border: 0;
    background: transparent;
    cursor: pointer;
    font: inherit;
    font-size: 0.8rem;
  }
  .selection-actions {
    padding: 0.25rem 0 0.75rem;
    gap: 0.75rem;
  }
  .primary-button,
  .quiet-button,
  .saved-job {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    border: 1px solid var(--glass-border);
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.1),
      rgba(var(--theme-rgb-surface-card), 0.5)
    );
    color: var(--theme-color-text-primary);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    text-decoration: none;
  }
  .primary-button {
    border-color: var(--theme-accent-color);
    color: var(--theme-accent-color);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.2),
      rgba(var(--theme-rgb-accent), 0.08)
    );
  }
  button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  button:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 2px;
  }
  .edit-actions {
    justify-content: space-between;
    width: 100%;
  }
  .output-details {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr);
    align-items: start;
    gap: 0.75rem;
  }
  .output-details label {
    display: grid;
    gap: 0.4rem;
    font-size: 0.85rem;
  }
  .output-details input,
  .output-details textarea {
    background: rgba(var(--theme-rgb-black), 0.2);
    color: inherit;
    border: 1px solid var(--glass-border);
    border-radius: 0.5rem;
    padding: 0.5rem;
    font: inherit;
    resize: vertical;
  }
  .error-message,
  .job-notice {
    padding: 0.75rem;
    border: 1px solid rgba(var(--theme-rgb-warning), 0.5);
    border-radius: 0.5rem;
    font-size: 0.85rem;
  }
  .upload-state,
  .import-start,
  .empty-result,
  .saved-jobs {
    display: grid;
    gap: 1rem;
  }
  .import-start {
    justify-items: center;
    padding: 2rem;
    text-align: center;
  }
  .saved-job {
    justify-content: space-between;
  }
  :global(.spinner) {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (max-width: 69rem) {
    .review-list {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
    }
    .selection-actions {
      gap: 0.5rem;
    }
    .list-row {
      flex: 0 1 auto;
      margin-bottom: 0;
      padding: 0.25rem 0.5rem;
    }
    .candidate-button {
      flex-direction: row;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 0.25rem 0.5rem;
    }
  }
  @media (max-width: 40rem) {
    .wizard-progress {
      font-size: 0.65rem;
    }
    .wizard-progress li {
      gap: 0.2rem;
    }
    .wizard-progress li:not(:last-child)::after {
      margin: 0 0.25rem;
    }
    .output-media,
    .output-details {
      grid-template-columns: minmax(0, 1fr);
    }
    .workflow {
      padding: 1rem;
    }
    .review-video {
      height: 24vh;
    }
    .edit-actions {
      gap: 0.5rem;
    }
  }
</style>
