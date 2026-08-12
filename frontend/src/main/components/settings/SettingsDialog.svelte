<script lang="ts">
  import { onDestroy, onMount, tick, untrack } from 'svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import { resolveRenderModeFromSections, setRenderMode } from '../../renderMode';
  import FieldItem from './FieldItem.svelte';
  import {
    collectSettingsUpdateSections,
    filterSettingsFieldsByDisplayMode,
    filterSettingsSectionsByDisplayMode,
    groupSettingsSections,
    type SettingsDisplayMode,
    type SettingsUiField,
    type SettingsUiSection,
  } from './grouping';
  import type { FieldValue, SettingField, SettingsResponse } from './types';
  import { calibrateAudio } from '../../../setup/stores/config';
  import { fetchRemoteAccessStatus, type RemoteAccessStatus } from '../../api/remoteAccess';
  import SpeechTestDialog from './SpeechTestDialog.svelte';

  const REMOTE_ACCESS_STATUS_REFRESH_INTERVAL_MS = 5000;
  const REMOTE_ACCESS_FALLBACK_PORT = 5173;
  const REMOTE_ACCESS_FIREWALL_COMMAND = [
    'New-NetFirewallRule `',
    '  -DisplayName "Allow TCP 5173 Inbound from LocalSubnet" `',
    '  -Direction Inbound `',
    '  -Action Allow `',
    '  -Protocol TCP `',
    '  -LocalPort 5173 `',
    '  -RemoteAddress LocalSubnet',
  ].join('\n');

  interface Props {
    open?: boolean;
  }

  let { open = $bindable(false) }: Props = $props();

  // 親コンポーネントと BaseDialog の bind:open を同期するために公開する。
  export { open };

  let sections = $state<SettingsUiSection[]>([]);
  let loading = $state(false);
  let saving = $state(false);
  let errorMessage = $state('');
  let successMessage = $state('');
  let activeSectionId = $state<string | null>(null);
  let successMessageTimer: ReturnType<typeof setTimeout> | null = null;
  let speechTestOpen = $state(false);
  let remoteAccessStatus = $state<RemoteAccessStatus | null>(null);
  let fieldsScrollElement = $state<HTMLDivElement | null>(null);
  let canScrollDown = $state(false);
  let displayMode = $state<SettingsDisplayMode>('basic');
  let useWideBasicColumns = $state(false);

  const activeSection = $derived(
    sections.find((section) => section.id === activeSectionId) ?? null
  );
  const visibleActiveFields = $derived(
    activeSection ? filterSettingsFieldsByDisplayMode(activeSection.fields, displayMode) : []
  );
  const basicSections = $derived(filterSettingsSectionsByDisplayMode(sections, 'basic'));
  const basicLeftSections = $derived(basicSections.filter((section) => section.id !== 'recording'));
  const basicRightSections = $derived(
    basicSections.filter((section) => section.id === 'recording')
  );
  const remoteAccessEnabledDraft = $derived(resolveRemoteAccessEnabled(sections));
  const showRemoteAccessSummary = $derived(
    (displayMode === 'basic'
      ? basicSections.some((section) =>
          section.fields.some((field) => field.sourceSectionId === 'remote_access')
        )
      : Boolean(activeSection?.sourceSectionIds.includes('remote_access'))) &&
      remoteAccessEnabledDraft === true
  );
  const remoteAccessEnabledForSummary = $derived(
    remoteAccessEnabledDraft ?? remoteAccessStatus?.enabled ?? false
  );
  const remoteAccessRestartRequired = $derived(
    remoteAccessStatus
      ? remoteAccessEnabledForSummary !== isRemoteAccessLanBound(remoteAccessStatus.bind_host)
      : false
  );
  const remoteAccessFallbackUrl = $derived(
    `http://<PCのIP>:${remoteAccessStatus?.port ?? REMOTE_ACCESS_FALLBACK_PORT}/`
  );

  $effect(() => {
    const renderedFieldCount =
      displayMode === 'basic'
        ? basicSections.reduce((count, section) => count + section.fields.length, 0)
        : visibleActiveFields.length;
    const shouldMeasure = displayMode === 'basic' || activeSectionId !== null;
    void renderedFieldCount;
    if (shouldMeasure) {
      void tick().then(updateScrollAffordance);
    } else {
      canScrollDown = false;
    }
  });

  // open の変化を監視し、ダイアログの開閉に応じて履歴を呼び出す
  // untrack で sections/loading を非依存にし、読み込んでも $effect が再実行されないようにする
  $effect(() => {
    if (open) {
      // untrack 内で読むことで sections/loading をトラッキング対象から除外し無限ループを防ぐ
      if (untrack(() => !loading && sections.length === 0)) {
        void loadSettings();
      }
    } else {
      handleDialogClose();
    }
  });

  $effect(() => {
    if (!open || !showRemoteAccessSummary || !remoteAccessEnabledForSummary) {
      return;
    }

    const intervalId = setInterval(() => {
      void loadRemoteAccessStatus();
    }, REMOTE_ACCESS_STATUS_REFRESH_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
    };
  });

  onDestroy(() => {
    clearSuccessMessageTimer();
  });

  onMount(() => {
    if (typeof window.matchMedia !== 'function') {
      return;
    }

    const wideBasicLayoutQuery = window.matchMedia('(min-width: 40.001rem)');
    const updateWideBasicLayout = (): void => {
      useWideBasicColumns = wideBasicLayoutQuery.matches;
    };

    updateWideBasicLayout();
    wideBasicLayoutQuery.addEventListener('change', updateWideBasicLayout);

    return () => {
      wideBasicLayoutQuery.removeEventListener('change', updateWideBasicLayout);
    };
  });

  function clearSuccessMessageTimer(): void {
    if (successMessageTimer !== null) {
      clearTimeout(successMessageTimer);
      successMessageTimer = null;
    }
  }

  function handleDialogClose(): void {
    resetState();
  }

  function resetState(): void {
    sections = [];
    loading = false;
    saving = false;
    errorMessage = '';
    successMessage = '';
    activeSectionId = null;
    speechTestOpen = false;
    remoteAccessStatus = null;
    displayMode = 'basic';
    clearSuccessMessageTimer();
  }

  function resolveRemoteAccessEnabled(sourceSections: SettingsUiSection[]): boolean | null {
    for (const section of sourceSections) {
      if (!section.sourceSectionIds.includes('remote_access')) {
        continue;
      }
      for (const field of section.fields) {
        if (field.id === 'enabled' && typeof field.value === 'boolean') {
          return field.value;
        }
        if (field.id === 'remote_access' && field.children) {
          const enabledField = field.children.find((child) => child.id === 'enabled');
          if (typeof enabledField?.value === 'boolean') {
            return enabledField.value;
          }
        }
      }
    }
    return null;
  }

  async function loadRemoteAccessStatus(): Promise<void> {
    try {
      remoteAccessStatus = await fetchRemoteAccessStatus();
    } catch {
      remoteAccessStatus = null;
    }
  }

  function isRemoteAccessLanBound(bindHost: string): boolean {
    return ['0.0.0.0', '::', '::0'].includes(bindHost.trim().toLowerCase());
  }

  async function loadSettings(): Promise<void> {
    loading = true;
    errorMessage = '';
    successMessage = '';
    remoteAccessStatus = null;
    clearSuccessMessageTimer();
    try {
      const response = await fetch('/api/settings', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`failed with status ${response.status}`);
      }
      const data = (await response.json()) as SettingsResponse;
      // 浅いコピーを作成してから フィルタリング（参照の共有を避ける）
      const sectionsClone = data.sections.map((section) => ({
        ...section,
        fields: section.fields.map((field) => ({ ...field })),
      }));
      sections = groupSettingsSections(sectionsClone);
      activeSectionId = sections[0]?.id ?? null;
      if (resolveRemoteAccessEnabled(sections) === true) {
        void loadRemoteAccessStatus();
      }
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : '設定の取得に失敗しました。';
      sections = [];
      activeSectionId = null;
    } finally {
      loading = false;
    }

    // キャッシュなしで最新のデバイス選択肢を取得し、表示中の選択肢を更新する
    void refreshDeviceChoices();
  }

  async function refreshDeviceChoices(): Promise<void> {
    try {
      const response = await fetch('/api/settings?refresh=true', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as SettingsResponse;
      const freshClone = data.sections.map((section) => ({
        ...section,
        fields: section.fields.map((field) => ({ ...field })),
      }));
      const freshSections = groupSettingsSections(freshClone);
      sections = mergeDeviceChoices(sections, freshSections);
    } catch {
      // デバイス選択肢の更新失敗は無視する（初回データで表示を継続）
    }
  }

  function mergeDeviceChoices(
    current: SettingsUiSection[],
    fresh: SettingsUiSection[]
  ): SettingsUiSection[] {
    const freshMap = new Map(fresh.map((s) => [s.id, s]));
    let changed = false;

    const merged = current.map((section) => {
      const freshSection = freshMap.get(section.id);
      if (!freshSection) {
        return section;
      }
      const mergedFields = mergeUiFieldChoices(section.fields, freshSection.fields);
      if (mergedFields !== section.fields) {
        changed = true;
        return { ...section, fields: mergedFields };
      }
      return section;
    });

    return changed ? merged : current;
  }

  function mergeUiFieldChoices(
    currentFields: SettingsUiField[],
    freshFields: SettingsUiField[]
  ): SettingsUiField[] {
    const freshMap = new Map(
      freshFields.map((field) => [`${field.sourceSectionId}:${field.id}`, field])
    );
    let changed = false;

    const merged = currentFields.map((field) => {
      const freshField = freshMap.get(`${field.sourceSectionId}:${field.id}`);
      if (!freshField) {
        return field;
      }

      if (field.children && freshField.children) {
        const mergedChildren = mergeFieldChoices(field.children, freshField.children);
        if (mergedChildren !== field.children) {
          changed = true;
          return { ...field, children: mergedChildren };
        }
        return field;
      }

      if (freshField.choices && !arraysEqual(field.choices, freshField.choices)) {
        changed = true;
        return { ...field, choices: freshField.choices };
      }

      return field;
    });

    return changed ? merged : currentFields;
  }

  function mergeFieldChoices(
    currentFields: SettingField[],
    freshFields: SettingField[]
  ): SettingField[] {
    const freshMap = new Map(freshFields.map((f) => [f.id, f]));
    let changed = false;

    const merged = currentFields.map((field) => {
      const freshField = freshMap.get(field.id);
      if (!freshField) {
        return field;
      }

      // 子フィールドがあるグループ型の場合は再帰
      if (field.children && freshField.children) {
        const mergedChildren = mergeFieldChoices(field.children, freshField.children);
        if (mergedChildren !== field.children) {
          changed = true;
          return { ...field, children: mergedChildren };
        }
        return field;
      }

      // choices が変わった場合のみ更新する
      if (freshField.choices && !arraysEqual(field.choices, freshField.choices)) {
        changed = true;
        return { ...field, choices: freshField.choices };
      }

      return field;
    });

    return changed ? merged : currentFields;
  }

  function arraysEqual(a: string[] | null | undefined, b: string[] | null | undefined): boolean {
    if (a === b) return true;
    if (!a || !b) return false;
    if (a.length !== b.length) return false;
    return a.every((val, i) => val === b[i]);
  }

  function selectSection(sectionId: string): void {
    activeSectionId = sectionId;
    canScrollDown = false;
    void tick().then(updateScrollAffordance);
  }

  function selectDisplayMode(mode: SettingsDisplayMode): void {
    if (displayMode === mode) {
      return;
    }

    displayMode = mode;
    canScrollDown = false;
    if (fieldsScrollElement) {
      fieldsScrollElement.scrollTop = 0;
    }
    void tick().then(updateScrollAffordance);
  }

  function settingsTabId(sectionId: string): string {
    return `settings-tab-${sectionId}`;
  }

  function settingsPanelId(sectionId: string): string {
    return `settings-panel-${sectionId}`;
  }

  function handleSectionKeydown(event: KeyboardEvent, currentIndex: number): void {
    let targetIndex: number | null = null;

    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      targetIndex = (currentIndex + 1) % sections.length;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      targetIndex = (currentIndex - 1 + sections.length) % sections.length;
    } else if (event.key === 'Home') {
      targetIndex = 0;
    } else if (event.key === 'End') {
      targetIndex = sections.length - 1;
    }

    if (targetIndex === null) {
      return;
    }

    const targetSection = sections[targetIndex];
    if (!targetSection) {
      return;
    }

    event.preventDefault();
    selectSection(targetSection.id);
    void tick().then(() => document.getElementById(settingsTabId(targetSection.id))?.focus());
  }

  function updateScrollAffordance(): void {
    if (!fieldsScrollElement) {
      canScrollDown = false;
      return;
    }

    const remainingScroll =
      fieldsScrollElement.scrollHeight -
      fieldsScrollElement.scrollTop -
      fieldsScrollElement.clientHeight;
    canScrollDown = remainingScroll > 1;
  }

  function handleFieldsScroll(): void {
    updateScrollAffordance();
  }

  function isLastFieldFromSource(
    fields: SettingsUiField[],
    fieldIndex: number,
    sourceSectionId: string
  ): boolean {
    return !fields.slice(fieldIndex + 1).some((field) => field.sourceSectionId === sourceSectionId);
  }

  function handleFieldValueChange(field: SettingField, value: FieldValue): void {
    // Immutable更新: field.valueを変更後、sections全体を再構築
    field.value = value;
    sections = sections.map((section) => ({
      ...section,
      fields: section.fields.map((f) => ({ ...f })),
    }));
  }

  function handleGroupFieldValueChange(
    group: SettingField,
    child: SettingField,
    value: FieldValue
  ): void {
    child.value = value;
    if (!group.value || typeof group.value !== 'object' || Array.isArray(group.value)) {
      group.value = {};
    }
    (group.value as Record<string, FieldValue>)[child.id] = value;
    // Immutable更新: sections全体を再構築
    sections = sections.map((section) => ({
      ...section,
      fields: section.fields.map((f) => ({
        ...f,
        children: f.children ? f.children.map((c) => ({ ...c })) : undefined,
      })),
    }));
  }

  async function handleCalibrateAudio(
    field: SettingField,
    parentGroup: SettingField | null = null
  ): Promise<void> {
    let micDeviceName = '';
    const recordingSection = sections.find((s) => s.id === 'recording');
    if (recordingSection) {
      const stGroup = recordingSection.fields.find((f) => f.id === 'speech_transcriber');
      const micField = stGroup?.children?.find((f) => f.id === 'mic_device_name');
      micDeviceName = (micField?.value as string) || '';
    } else {
      const stSection = sections.find((s) => s.id === 'speech_transcriber');
      const micField = stSection?.fields.find((f) => f.id === 'mic_device_name');
      micDeviceName = (micField?.value as string) || '';
    }

    if (!micDeviceName) {
      throw new Error('マイクデバイスが選択されていません。設定を保存してから再度お試しください。');
    }

    saving = true;
    try {
      const threshold = await calibrateAudio(micDeviceName);
      if (parentGroup) {
        handleGroupFieldValueChange(parentGroup, field, threshold);
      } else {
        handleFieldValueChange(field, threshold);
      }
    } finally {
      saving = false;
    }
  }

  function getSpeechTranscriberSettings(): Record<string, unknown> {
    const recordingSection = sections.find((s) => s.id === 'recording');
    if (recordingSection) {
      const stGroup = recordingSection.fields.find((f) => f.id === 'speech_transcriber');
      if (stGroup?.children) {
        const values: Record<string, unknown> = {};
        for (const child of stGroup.children) {
          if (child.value !== undefined && child.value !== null) {
            values[child.id] = child.value;
          }
        }
        return values;
      }
    }
    const stSection = sections.find((s) => s.id === 'speech_transcriber');
    if (stSection) {
      const values: Record<string, unknown> = {};
      for (const field of stSection.fields) {
        if (field.value !== undefined && field.value !== null) {
          values[field.id] = field.value;
        }
      }
      return values;
    }
    return {};
  }

  function handleTestSpeech(): void {
    speechTestOpen = true;
  }

  const speechTestSettings = $derived(getSpeechTranscriberSettings());

  async function saveSettings(): Promise<void> {
    if (saving || loading) {
      return;
    }
    saving = true;
    errorMessage = '';
    successMessage = '';
    clearSuccessMessageTimer();
    try {
      const payload = {
        sections: collectSettingsUpdateSections(sections),
      };
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        let detail = `failed with status ${response.status}`;
        try {
          const body = await response.json();
          if (typeof body.detail === 'string') {
            detail = body.detail;
          }
        } catch {
          detail = `failed with status ${response.status}`;
        }
        throw new Error(detail);
      }
      const nextRenderMode = resolveRenderModeFromSections(sections);
      if (nextRenderMode !== null) {
        setRenderMode(nextRenderMode);
      }
      open = false;
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : '設定の保存に失敗しました。';
    } finally {
      saving = false;
    }
  }

  async function handlePrimaryClick(): Promise<void> {
    await saveSettings();
  }

  function handleSecondaryClick(): void {
    open = false;
  }
</script>

{#snippet remoteAccessSummary()}
  {#if showRemoteAccessSummary}
    <div class="remote-access-summary" data-testid="remote-access-summary">
      <div class="remote-access-row">
        <span>LAN 公開</span>
        <strong>{remoteAccessEnabledForSummary ? '有効' : '無効'}</strong>
      </div>
      {#if remoteAccessRestartRequired}
        <p>変更はアプリ再起動後に反映されます。</p>
      {:else if remoteAccessStatus?.active && remoteAccessStatus.access_urls.length}
        <p>現在、家庭内LANから接続できます。</p>
      {:else if remoteAccessStatus?.active}
        <p>スマホから接続できるLAN URLを確認できません。</p>
      {:else}
        <p>初期状態ではPC内からのみ接続できます。</p>
      {/if}
      {#if remoteAccessStatus?.active && remoteAccessStatus.access_urls.length}
        <div class="remote-access-urls" aria-label="スマホで開くURL候補">
          {#each remoteAccessStatus.access_urls as url}
            <code>{url}</code>
          {/each}
        </div>
      {:else if remoteAccessRestartRequired}
        <p>再起動後、LAN公開が反映されるとURL候補を表示します。</p>
      {:else if remoteAccessStatus?.active}
        <p>Windows Firewallやネットワーク設定を確認してください。</p>
      {:else}
        <p>
          有効化後、PCのIPアドレスで <code class="remote-access-inline-code"
            >{remoteAccessFallbackUrl}</code
          > を開きます。
        </p>
      {/if}
      <div class="remote-access-help" style="text-align: left">
        <p>Wi-Fiをプライベートネットワークに設定してください。</p>
        <p>ファイアウォールは管理者権限のPowerShellで以下を実行してください。</p>
        <pre class="remote-access-command"><code>{REMOTE_ACCESS_FIREWALL_COMMAND}</code></pre>
      </div>
    </div>
  {/if}
{/snippet}

{#snippet basicSettingsSection(section: SettingsUiSection)}
  <section
    class="basic-settings-section"
    aria-labelledby={`settings-basic-section-${section.id}`}
    data-testid={`settings-section-${section.id}`}
  >
    <h3 id={`settings-basic-section-${section.id}`}>{section.label}</h3>
    <div class="basic-section-fields">
      {#each section.fields as field, fieldIndex (`${field.sourceSectionId}:${field.id}`)}
        {#if field.type === 'group' && field.children}
          {#each field.children as child (child.id)}
            <FieldItem
              field={child}
              sectionId={section.id}
              path={[field.sourceSectionId]}
              updateField={handleFieldValueChange}
              updateGroupField={handleGroupFieldValueChange}
              parentGroup={field}
              onCalibrateAudio={handleCalibrateAudio}
              onTestSpeech={handleTestSpeech}
            />
          {/each}
        {:else}
          <FieldItem
            {field}
            sectionId={section.id}
            path={field.id === field.sourceSectionId ? [] : [field.sourceSectionId]}
            variant="flat"
            updateField={handleFieldValueChange}
            updateGroupField={handleGroupFieldValueChange}
            parentGroup={null}
            onCalibrateAudio={handleCalibrateAudio}
            onTestSpeech={handleTestSpeech}
          />
        {/if}
        {#if field.sourceSectionId === 'remote_access' && isLastFieldFromSource(section.fields, fieldIndex, 'remote_access')}
          {@render remoteAccessSummary()}
        {/if}
      {/each}
    </div>
  </section>
{/snippet}

{#snippet settingsHeader()}
  <div class="settings-dialog-header">
    <h2 id="dialog-title">設定</h2>
    <fieldset class="display-mode-switch">
      <legend class="sr-only">設定項目の表示範囲</legend>
      <label class:selected={displayMode === 'basic'}>
        <input
          type="radio"
          name="settings-display-mode"
          value="basic"
          checked={displayMode === 'basic'}
          onchange={() => selectDisplayMode('basic')}
        />
        <span>基本設定</span>
      </label>
      <label class:selected={displayMode === 'all'}>
        <input
          type="radio"
          name="settings-display-mode"
          value="all"
          checked={displayMode === 'all'}
          onchange={() => selectDisplayMode('all')}
        />
        <span>すべての設定</span>
      </label>
    </fieldset>
  </div>
{/snippet}

<BaseDialog
  bind:open
  title="設定"
  footerVariant="simple"
  primaryButtonText={saving ? '保存中...' : '保存'}
  secondaryButtonText="キャンセル"
  disablePrimaryButton={saving || loading}
  disableSecondaryButton={saving}
  onPrimaryClick={handlePrimaryClick}
  onSecondaryClick={handleSecondaryClick}
  maxWidth="60rem"
  maxHeight="90vh"
  minHeight="90vh"
  mobileFullscreen={true}
>
  {#snippet header()}
    {@render settingsHeader()}
  {/snippet}

  {#if loading}
    <div class="loading-state" role="status" aria-live="polite">
      <span
        class="loading-spinner settings-loading-spinner"
        aria-hidden="true"
        data-testid="settings-loading-spinner"
      ></span>
      <p class="status">読み込み中です...</p>
    </div>
  {:else if errorMessage && !sections.length}
    <p class="status error">{errorMessage}</p>
  {:else}
    <div
      class="dialog-content"
      class:basic-layout={displayMode === 'basic'}
      data-testid="settings-dialog-content"
    >
      {#if displayMode === 'basic'}
        <div
          class="fields"
          class:can-scroll-down={canScrollDown}
          role="region"
          aria-label="基本設定"
          data-testid="settings-fields"
        >
          <div
            class="fields-scroll"
            bind:this={fieldsScrollElement}
            onscroll={handleFieldsScroll}
            data-testid="settings-fields-scroll"
          >
            {#if basicSections.length > 0}
              {#if useWideBasicColumns}
                <div class="basic-settings-columns" data-testid="settings-basic-grid">
                  <div class="basic-settings-column" data-testid="settings-basic-left-column">
                    {#each basicLeftSections as section (section.id)}
                      {@render basicSettingsSection(section)}
                    {/each}
                  </div>
                  <div class="basic-settings-column" data-testid="settings-basic-right-column">
                    {#each basicRightSections as section (section.id)}
                      {@render basicSettingsSection(section)}
                    {/each}
                  </div>
                </div>
              {:else}
                <div class="basic-settings-list" data-testid="settings-basic-grid">
                  {#each basicSections as section (section.id)}
                    {@render basicSettingsSection(section)}
                  {/each}
                </div>
              {/if}
            {:else}
              <div class="empty-basic-state">
                <p>基本設定に表示する項目はありません。</p>
                <button type="button" onclick={() => selectDisplayMode('all')}>
                  すべての設定を表示
                </button>
              </div>
            {/if}
          </div>
        </div>
      {:else}
        <div class="tabs" role="tablist" aria-label="設定カテゴリ" data-testid="settings-tabs">
          {#each sections as section, index (section.id)}
            <button
              id={settingsTabId(section.id)}
              class:selected={section.id === activeSectionId}
              type="button"
              role="tab"
              aria-selected={section.id === activeSectionId}
              aria-controls={settingsPanelId(section.id)}
              tabindex={section.id === activeSectionId ? 0 : -1}
              onclick={() => selectSection(section.id)}
              onkeydown={(event) => handleSectionKeydown(event, index)}
              data-testid={`settings-section-${section.id}`}
            >
              {section.label}
            </button>
          {/each}
        </div>
        <div
          id={activeSection ? settingsPanelId(activeSection.id) : undefined}
          class="fields"
          class:can-scroll-down={canScrollDown}
          role="tabpanel"
          aria-labelledby={activeSection ? settingsTabId(activeSection.id) : undefined}
          data-testid="settings-fields"
        >
          {#if activeSection}
            <div
              class="fields-scroll"
              bind:this={fieldsScrollElement}
              onscroll={handleFieldsScroll}
              data-testid="settings-fields-scroll"
            >
              {#each visibleActiveFields as field, fieldIndex (`${field.sourceSectionId}:${field.id}`)}
                <FieldItem
                  {field}
                  sectionId={activeSection.id}
                  path={field.id === field.sourceSectionId ? [] : [field.sourceSectionId]}
                  updateField={handleFieldValueChange}
                  updateGroupField={handleGroupFieldValueChange}
                  parentGroup={null}
                  onCalibrateAudio={handleCalibrateAudio}
                  onTestSpeech={handleTestSpeech}
                />
                {#if field.sourceSectionId === 'remote_access' && isLastFieldFromSource(visibleActiveFields, fieldIndex, 'remote_access')}
                  {@render remoteAccessSummary()}
                {/if}
              {/each}
            </div>
          {:else}
            <p class="status">セクションを選択してください。</p>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  {#snippet footerStatus()}
    {#if errorMessage && sections.length}
      <p class="status error">{errorMessage}</p>
    {:else if successMessage}
      <p class="status success">{successMessage}</p>
    {/if}
  {/snippet}
</BaseDialog>

<SpeechTestDialog bind:open={speechTestOpen} speechSettings={speechTestSettings} />

<style>
  .settings-dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    width: 100%;
    min-width: 0;
  }

  .settings-dialog-header h2 {
    flex: 0 0 auto;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .display-mode-switch {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin: 0;
    padding: 0.1875rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.14);
    border-radius: 0.75rem;
    background: rgba(var(--theme-rgb-black), 0.2);
  }

  .display-mode-switch label {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 7.5rem;
    padding: 0.55rem 0.8rem;
    border-radius: 0.5625rem;
    color: rgba(var(--theme-rgb-light-slate), 0.72);
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition:
      color 0.18s ease,
      background 0.18s ease,
      box-shadow 0.18s ease;
  }

  .display-mode-switch label:hover {
    color: rgba(var(--theme-rgb-white), 0.94);
  }

  .display-mode-switch label.selected {
    color: rgba(var(--theme-rgb-white), 0.98);
    background: rgba(var(--theme-rgb-accent), 0.22);
    box-shadow:
      0 0.2rem 0.7rem rgba(var(--theme-rgb-black), 0.2),
      inset 0 0 0 1px rgba(var(--theme-rgb-accent), 0.32);
  }

  .display-mode-switch label:has(input:focus-visible) {
    outline: 0.125rem solid rgba(var(--theme-rgb-accent), 0.7);
    outline-offset: 0.125rem;
  }

  .display-mode-switch input {
    position: absolute;
    inset: 0;
    z-index: 1;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    cursor: pointer;
  }

  .dialog-content {
    display: grid;
    grid-template-columns: 13.75rem 1fr;
    gap: 2rem;
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    align-items: stretch;
    overflow: hidden;
  }

  .dialog-content.basic-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .basic-settings-columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
    gap: 1rem;
  }

  .basic-settings-column,
  .basic-settings-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-width: 0;
  }

  .basic-settings-section {
    min-width: 0;
    padding: 1.25rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.12);
    border-radius: 1rem;
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-surface-card), 0.94) 0%,
      rgba(var(--theme-rgb-surface-card-dark), 0.9) 100%
    );
    box-shadow:
      0 0.45rem 1.2rem rgba(var(--theme-rgb-black), 0.18),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.1);
  }

  .basic-settings-section h3 {
    margin: 0 0 0.25rem;
    color: rgba(var(--theme-rgb-white), 0.96);
    font-size: 1.05rem;
    font-weight: 700;
  }

  .basic-section-fields {
    display: flex;
    flex-direction: column;
  }

  .basic-section-fields :global(.field-item:last-child) {
    border-bottom: 0;
  }

  .tabs {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    overflow-y: auto;
    overflow-x: hidden;
    min-height: 0;
    align-self: start;
  }

  .tabs button {
    border: none;
    background: transparent;
    color: rgba(var(--theme-rgb-light-slate), 0.7);
    border-radius: 0.625rem;
    padding: 0.85rem 1.2rem;
    text-align: left;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    transition:
      color 0.22s ease,
      background 0.22s ease,
      box-shadow 0.22s ease;
    flex: 0 0 auto;
    width: 100%;
    position: relative;
  }

  .tabs button:hover {
    background: rgba(var(--theme-rgb-accent), 0.06);
    color: rgba(var(--theme-rgb-white), 0.95);
  }

  .tabs button.selected {
    background: rgba(var(--theme-rgb-accent), 0.15);
    color: rgba(var(--theme-rgb-white), 0.95);
    font-weight: 600;
  }

  .tabs button.selected::after {
    content: '';
    position: absolute;
    left: 0;
    top: 20%;
    bottom: 20%;
    width: 3px;
    background: var(--accent-color);
    border-radius: 0 3px 3px 0;
    box-shadow: 0 0 8px rgba(var(--theme-rgb-accent), 0.6);
    animation: tab-indicator-glow 0.2s cubic-bezier(0.2, 0, 0, 1) forwards;
  }

  .tabs button:focus-visible {
    outline: 0.125rem solid rgba(var(--theme-rgb-accent), 0.7);
    outline-offset: 0.125rem;
  }

  @keyframes tab-indicator-glow {
    from {
      transform: scaleY(0);
      opacity: 0;
    }
    to {
      transform: scaleY(1);
      opacity: 1;
    }
  }

  .fields {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
    height: 100%;
    overflow: hidden;
  }

  .fields::after {
    content: '';
    position: absolute;
    right: 1rem;
    bottom: 0;
    left: 0;
    height: 3.5rem;
    background: linear-gradient(
      180deg,
      rgba(var(--theme-rgb-surface-card-dark), 0) 0%,
      rgba(var(--theme-rgb-surface-card-dark), 0.96) 100%
    );
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.18s ease;
  }

  .fields.can-scroll-down::after {
    opacity: 1;
  }

  .fields-scroll {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    overflow-y: auto;
    overflow-x: hidden;
    max-height: 100%;
    padding: 0.25rem 1rem 0.25rem 0.25rem;
    flex: 1 1 auto;
    height: 100%;
    min-height: 0;
    scrollbar-color: rgba(var(--theme-rgb-accent), 0.65) rgba(var(--theme-rgb-white), 0.08);
  }

  .empty-basic-state {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.9rem;
    padding: 1.25rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.12);
    border-radius: 0.875rem;
    background: rgba(var(--theme-rgb-white), 0.04);
  }

  .empty-basic-state p {
    margin: 0;
    color: rgba(var(--theme-rgb-light-slate), 0.8);
  }

  .empty-basic-state button {
    border: 1px solid rgba(var(--theme-rgb-accent), 0.36);
    border-radius: 0.625rem;
    padding: 0.65rem 0.9rem;
    background: rgba(var(--theme-rgb-accent), 0.12);
    color: var(--accent-color);
    font-weight: 600;
    cursor: pointer;
  }

  .empty-basic-state button:hover {
    background: rgba(var(--theme-rgb-accent), 0.2);
  }

  .empty-basic-state button:focus-visible {
    outline: 0.125rem solid rgba(var(--theme-rgb-accent), 0.7);
    outline-offset: 0.125rem;
  }

  .remote-access-summary {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    text-align: left;
    padding: 1rem 1.125rem;
    border-left: 3px solid var(--accent-color);
    background: rgba(var(--theme-rgb-accent), 0.08);
    color: rgba(var(--theme-rgb-white), 0.86);
    font-size: 0.9rem;
    line-height: 1.55;
  }

  .remote-access-summary p {
    margin: 0;
  }

  .remote-access-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .remote-access-row strong {
    color: rgba(var(--theme-rgb-white), 0.96);
    font-weight: 700;
    white-space: nowrap;
  }

  .remote-access-urls {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .remote-access-urls code {
    width: fit-content;
    max-width: 100%;
    overflow-wrap: anywhere;
    color: rgba(var(--theme-rgb-white), 0.94);
    background: rgba(var(--theme-rgb-black), 0.3);
    padding: 0.35rem 0.5rem;
    border-radius: 0.375rem;
  }

  .remote-access-inline-code {
    overflow-wrap: anywhere;
    color: rgba(var(--theme-rgb-white), 0.94);
    background: rgba(var(--theme-rgb-black), 0.3);
    padding: 0.16rem 0.35rem;
    border-radius: 0.3rem;
  }

  .remote-access-help {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0.45rem;
    text-align: left;
  }

  .remote-access-command {
    margin: 0;
    max-width: 100%;
    text-align: left;
    overflow-x: auto;
    padding: 0.75rem;
    border-radius: 0.5rem;
    background: rgba(var(--theme-rgb-black), 0.32);
    border: 1px solid rgba(var(--theme-rgb-white), 0.1);
  }

  .remote-access-command code {
    color: rgba(var(--theme-rgb-white), 0.94);
    font-size: 0.82rem;
    line-height: 1.5;
    white-space: pre;
  }

  .fields-scroll::-webkit-scrollbar {
    width: 0.625rem;
  }

  .fields-scroll::-webkit-scrollbar-track {
    background: rgba(var(--theme-rgb-white), 0.08);
    border-radius: 999px;
  }

  .fields-scroll::-webkit-scrollbar-thumb {
    background: linear-gradient(
      180deg,
      rgba(var(--theme-rgb-accent), 0.76) 0%,
      rgba(var(--theme-rgb-accent), 0.52) 100%
    );
    border: 2px solid rgba(var(--theme-rgb-surface-card-dark), 0.9);
    border-radius: 999px;
    transition: background 0.2s ease;
  }

  .fields-scroll::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(
      180deg,
      rgba(var(--theme-rgb-accent), 0.7) 0%,
      rgba(var(--theme-rgb-accent), 0.5) 100%
    );
  }

  .status {
    margin: 0;
    font-size: 0.9rem;
    color: rgba(var(--theme-rgb-white), 0.8);
    padding: 0.5rem 0;
  }

  .loading-state {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.9rem;
    min-height: 0;
  }

  .settings-loading-spinner {
    width: 2rem;
    height: 2rem;
    box-sizing: border-box;
    border: 0.2rem solid rgba(var(--theme-rgb-white), 0.14);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    filter: drop-shadow(0 0 0.4rem rgba(var(--theme-rgb-accent), 0.35));
  }

  .status.error {
    color: var(--theme-status-danger-soft);
    text-shadow: 0 0 0.3rem rgba(var(--theme-rgb-danger-soft-alt), 0.18);
  }

  .status.success {
    color: var(--theme-status-success-soft);
    text-shadow: 0 0 0.3rem rgba(var(--theme-rgb-success-soft-alt), 0.16);
  }

  @media (max-width: 56.25rem) {
    .dialog-content {
      grid-template-columns: 1fr;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 1rem;
      height: 100%;
    }

    .tabs {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 0.5rem;
      padding: 0.25rem;
      overflow: visible;
    }

    .tabs button {
      width: auto;
      min-width: 0;
      padding: 0.75rem 0.5rem;
      text-align: center;
      white-space: nowrap;
    }
  }

  @media (max-width: 40rem) {
    .settings-dialog-header {
      flex-direction: column;
      align-items: stretch;
      gap: 0.65rem;
    }

    .display-mode-switch {
      width: 100%;
      box-sizing: border-box;
    }

    .display-mode-switch label {
      min-width: 0;
    }

    .dialog-content {
      height: 100%;
      max-height: none;
      padding: 1rem;
      gap: 0.75rem;
    }

    .basic-settings-section {
      padding: 1rem;
    }

    .tabs {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .tabs button {
      padding: 0.7rem 0.45rem;
      font-size: 0.85rem;
    }

    .fields,
    .fields-scroll {
      width: 100%;
      max-width: 100%;
      height: 100%;
      max-height: none;
    }

    .fields-scroll {
      padding: 0.25rem 0.75rem 0.25rem 0;
    }

    .fields::after {
      right: 0.75rem;
    }

    .remote-access-row {
      align-items: flex-start;
      flex-direction: column;
      gap: 0.5rem;
    }
  }

  @media (max-width: 22rem) {
    .dialog-content {
      padding: 0.75rem;
    }

    .tabs button {
      padding: 0.65rem 0.35rem;
      font-size: 0.8rem;
    }
  }
</style>
