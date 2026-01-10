<script lang="ts">
  import BaseDialog from '../../../common/components/BaseDialog.svelte';
  import FieldItem from './FieldItem.svelte';
  import type { FieldValue, SettingField, SettingsResponse, SettingsSection } from './types';

  export let open = false;

  let sections: SettingsSection[] = [];
  let loading = false;
  let saving = false;
  let loaded = false;
  let errorMessage = '';
  let successMessage = '';
  let activeSectionId: string | null = null;

  $: activeSection = sections.find((section) => section.id === activeSectionId) ?? null;

  $: if (open && !loaded && !loading) {
    void loadSettings();
  }

  $: if (!open && loaded) {
    resetState();
  }

  function resetState(): void {
    sections = [];
    loading = false;
    saving = false;
    loaded = false;
    errorMessage = '';
    successMessage = '';
    activeSectionId = null;
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
    try {
      const response = await fetch('/api/settings', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`failed with status ${response.status}`);
      }
      const data = (await response.json()) as SettingsResponse;
      const sectionsData = data.sections;
      const sectionsClone =
        typeof structuredClone === 'function'
          ? structuredClone(sectionsData)
          : (JSON.parse(JSON.stringify(sectionsData)) as SettingsSection[]);
      sections = filterEditableSections(sectionsClone);
      activeSectionId = sections[0]?.id ?? null;
      loaded = true;
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : '設定の取得に失敗しました。';
    } finally {
      loading = false;
    }
  }

  function selectSection(sectionId: string): void {
    activeSectionId = sectionId;
  }

  function handleFieldValueChange(field: SettingField, value: FieldValue): void {
    field.value = value;
    sections = sections;
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
    sections = sections;
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
      successMessage = '設定を保存しました。';
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : '設定の保存に失敗しました。';
    } finally {
      saving = false;
    }
  }

  async function handlePrimaryClick(): Promise<void> {
    await saveSettings();
    if (!errorMessage) {
      open = false;
    }
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
  on:primary-click={handlePrimaryClick}
  on:secondary-click={handleSecondaryClick}
  maxWidth="60rem"
  maxHeight="90vh"
>
  {#if loading}
    <p class="status">読み込み中です...</p>
  {:else if errorMessage && !sections.length}
    <p class="status error">{errorMessage}</p>
  {:else}
    <div class="dialog-content">
      <nav class="tabs">
        {#each sections as section (section.id)}
          <button
            class:selected={section.id === activeSectionId}
            type="button"
            on:click={() => selectSection(section.id)}
          >
            {section.label}
          </button>
        {/each}
      </nav>
      <div class="fields">
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

  <svelte:fragment slot="footer-status">
    {#if errorMessage && sections.length}
      <p class="status error">{errorMessage}</p>
    {:else if successMessage}
      <p class="status success">{successMessage}</p>
    {/if}
  </svelte:fragment>
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
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.06) 0%,
      rgba(255, 255, 255, 0.03) 100%
    );
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.8);
    border-radius: 0.625rem;
    padding: 0.85rem 1.2rem;
    text-align: left;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    flex: 0 0 auto;
    width: 100%;
  }

  .tabs button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.1) 50%,
      transparent 100%
    );
    transition: left 0.6s ease;
  }

  .tabs button:hover::before {
    left: 100%;
  }

  .tabs button:hover {
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.15) 0%, rgba(25, 211, 199, 0.08) 100%);
    border-color: rgba(25, 211, 199, 0.3);
    color: #19d3c7;
    transform: translateX(0.25rem);
  }

  .tabs button.selected {
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.25) 0%, rgba(25, 211, 199, 0.15) 100%);
    border-color: rgba(25, 211, 199, 0.4);
    color: #19d3c7;
    box-shadow:
      0 0.25rem 0.75rem rgba(25, 211, 199, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
    font-weight: 600;
  }

  .fields {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.06) 0%,
      rgba(255, 255, 255, 0.03) 100%
    );
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 1rem;
    padding: 2rem;
    box-shadow:
      0 0.5rem 1.5rem rgba(0, 0, 0, 0.2),
      0 0.125rem 0.5rem rgba(0, 0, 0, 0.1),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
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
    background: rgba(255, 255, 255, 0.05);
    border-radius: 0.1875rem;
  }

  .fields-scroll::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, rgba(25, 211, 199, 0.5) 0%, rgba(25, 211, 199, 0.3) 100%);
    border-radius: 0.1875rem;
    transition: background 0.2s ease;
  }

  .fields-scroll::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, rgba(25, 211, 199, 0.7) 0%, rgba(25, 211, 199, 0.5) 100%);
  }

  .status {
    margin: 0;
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.8);
    padding: 0.5rem 0;
  }

  .status.error {
    color: #ff6b6b;
    text-shadow: 0 0 0.5rem rgba(255, 107, 107, 0.3);
  }

  .status.success {
    color: #34d399;
    text-shadow: 0 0 0.5rem rgba(52, 211, 153, 0.3);
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
