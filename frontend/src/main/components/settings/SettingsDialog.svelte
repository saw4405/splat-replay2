<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import { resolveRenderModeFromSections, setRenderMode } from '../../renderMode';
  import FieldItem from './FieldItem.svelte';
  import type { FieldValue, SettingField, SettingsResponse, SettingsSection } from './types';

  interface Props {
    open?: boolean;
  }

  let { open = $bindable(false) }: Props = $props();

  // テストから component.open でアクセスできるように export
  export { open };

  let sections = $state<SettingsSection[]>([]);
  let loading = $state(false);
  let saving = $state(false);
  let errorMessage = $state('');
  let successMessage = $state('');
  let activeSectionId = $state<string | null>(null);
  let successMessageTimer: ReturnType<typeof setTimeout> | null = null;

  const activeSection = $derived(
    sections.find((section) => section.id === activeSectionId) ?? null
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
    clearSuccessMessageTimer();
  }

  function filterEditableFields(fields: SettingField[]): SettingField[] {
    const result: SettingField[] = [];
    for (const field of fields) {
      if (field.type === 'group' && field.children) {
        const children = filterEditableFields(field.children);
        if (children.length > 0) {
          result.push({ ...field, children });
        }
        continue;
      }
      if (field.user_editable) {
        result.push(field);
      }
    }
    return result;
  }

  function filterEditableSections(sectionsData: SettingsSection[]): SettingsSection[] {
    return sectionsData
      .map((section) => {
        const fields = filterEditableFields(section.fields);
        return { ...section, fields };
      })
      .filter((section) => section.fields.length > 0);
  }

  async function loadSettings(): Promise<void> {
    loading = true;
    errorMessage = '';
    successMessage = '';
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
      sections = filterEditableSections(sectionsClone);
      activeSectionId = sections[0]?.id ?? null;
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : '設定の取得に失敗しました。';
      sections = [];
      activeSectionId = null;
    } finally {
      loading = false;
    }
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

  function collectSectionValues(section: SettingsSection): Record<string, FieldValue> {
    const values: Record<string, FieldValue> = {};
    for (const field of section.fields) {
      values[field.id] = collectFieldValue(field);
    }
    return values;
  }

  function collectFieldValue(field: SettingField): FieldValue {
    if (field.type === 'group' && field.children) {
      return collectGroupValues(field.children);
    }
    if (field.type === 'list') {
      return Array.isArray(field.value) ? field.value : [];
    }
    if (typeof field.value === 'undefined' || field.value === null) {
      if (field.type === 'boolean') {
        return false;
      }
      if (field.type === 'integer' || field.type === 'float') {
        return 0;
      }
      return '';
    }
    return field.value;
  }

  function collectGroupValues(fields: SettingField[]): Record<string, FieldValue> {
    const result: Record<string, FieldValue> = {};
    for (const child of fields) {
      result[child.id] = collectFieldValue(child);
    }
    return result;
  }

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
        sections: sections.map((section) => ({
          id: section.id,
          values: collectSectionValues(section),
        })),
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
    padding: 0rem 0.5rem;
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
      flex: 1 0 auto;
      text-align: center;
    }
  }
</style>
