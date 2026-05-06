<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import { resolveRenderModeFromSections, setRenderMode } from '../../renderMode';
  import FieldItem from './FieldItem.svelte';
  import {
    collectSettingsUpdateSections,
    groupSettingsSections,
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

  // テストから component.open でアクセスできるように export
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

  const activeSection = $derived(
    sections.find((section) => section.id === activeSectionId) ?? null
  );
  const remoteAccessEnabledDraft = $derived(resolveRemoteAccessEnabled(sections));
  const showRemoteAccessSummary = $derived(
    Boolean(activeSection?.sourceSectionIds.includes('remote_access')) &&
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
      const mergedFields = mergeFieldChoices(section.fields, freshSection.fields);
      if (mergedFields !== section.fields) {
        changed = true;
        return { ...section, fields: mergedFields };
      }
      return section;
    });

    return changed ? merged : current;
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

{#snippet remoteAccessGroupAddon(field: SettingField)}
  {#if field.id === 'remote_access' && showRemoteAccessSummary}
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
>
  {#if loading}
    <p class="status">読み込み中です...</p>
  {:else if errorMessage && !sections.length}
    <p class="status error">{errorMessage}</p>
  {:else}
    <div class="dialog-content">
      <nav class="tabs" data-testid="settings-tabs">
        {#each sections as section (section.id)}
          <button
            class:selected={section.id === activeSectionId}
            type="button"
            onclick={() => selectSection(section.id)}
            data-testid={`settings-section-${section.id}`}
          >
            {section.label}
          </button>
        {/each}
      </nav>
      <div class="fields" data-testid="settings-fields">
        {#if activeSection}
          <div class="fields-scroll">
            {#each activeSection.fields as field (field.id)}
              <FieldItem
                {field}
                sectionId={activeSection.id}
                path={[activeSection.id]}
                updateField={handleFieldValueChange}
                updateGroupField={handleGroupFieldValueChange}
                parentGroup={null}
                onCalibrateAudio={handleCalibrateAudio}
                onTestSpeech={handleTestSpeech}
                groupAddon={remoteAccessGroupAddon}
              />
            {/each}
          </div>
        {:else}
          <p class="status">セクションを選択してください。</p>
        {/if}
      </div>
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

  .tabs {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    overflow-y: auto;
    overflow-x: hidden;
    height: 100%;
    min-height: 0;
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
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-surface-card), 0.94) 0%,
      rgba(var(--theme-rgb-surface-card-dark), 0.9) 100%
    );
    backdrop-filter: blur(8px) saturate(135%);
    -webkit-backdrop-filter: blur(8px) saturate(135%);
    border: 1px solid rgba(var(--theme-rgb-white), 0.12);
    border-radius: 1rem;
    padding: 2rem;
    box-shadow:
      0 0.45rem 1.2rem rgba(var(--theme-rgb-black), 0.18),
      0 0.1rem 0.35rem rgba(var(--theme-rgb-black), 0.1),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.1);
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
    flex: 1 1 auto;
    overflow: hidden;
  }

  .fields-scroll {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    overflow-y: auto;
    max-height: 100%;
    padding-right: 0.5rem;
    flex: 1 1 auto;
    height: 100%;
    min-height: 0;
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
    width: 0.375rem;
  }

  .fields-scroll::-webkit-scrollbar-track {
    background: rgba(var(--theme-rgb-white), 0.05);
    border-radius: 0.1875rem;
  }

  .fields-scroll::-webkit-scrollbar-thumb {
    background: linear-gradient(
      180deg,
      rgba(var(--theme-rgb-accent), 0.5) 0%,
      rgba(var(--theme-rgb-accent), 0.3) 100%
    );
    border-radius: 0.1875rem;
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
    }

    .tabs {
      flex-direction: row;
      overflow-x: auto;
      padding-bottom: 0;
    }

    .tabs button {
      flex: 1 1 0;
      text-align: center;
      white-space: nowrap;
    }
  }
</style>
