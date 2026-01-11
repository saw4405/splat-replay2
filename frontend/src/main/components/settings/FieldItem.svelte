<script lang="ts">
  import { Eye, EyeOff } from 'lucide-svelte';
  import SelectField from './SelectField.svelte';
  import type { FieldValue, PrimitiveValue, SettingField } from './types';

  export let field: SettingField;
  export let sectionId: string;
  export let path: string[] = [];
  export let updateField: (field: SettingField, value: FieldValue) => void;
  export let updateGroupField: (
    group: SettingField,
    child: SettingField,
    value: FieldValue
  ) => void;
  export let parentGroup: SettingField | null = null;

  const pathTokens = [...path, field.id];
  const elementId = `${sectionId}-${pathTokens.join('-')}`;
  const labelElementId = `${elementId}-label`;
  const descriptionId = `${elementId}-description`;

  let showPassword = false;
  let listText = '';

  $: if (field.type === 'list') {
    listText = Array.isArray(field.value) ? field.value.join('\n') : '';
  }

  function commitPrimitive(value: PrimitiveValue): void {
    if (parentGroup) {
      updateGroupField(parentGroup, field, value);
    } else {
      updateField(field, value);
    }
  }

  function _commitField(value: FieldValue): void {
    if (parentGroup) {
      updateGroupField(parentGroup, field, value);
    } else {
      updateField(field, value);
    }
  }

  function commitInteger(event: Event): void {
    const target = event.currentTarget as HTMLInputElement;
    const parsed = Number.parseInt(target.value, 10);
    commitPrimitive(Number.isNaN(parsed) ? 0 : parsed);
  }

  function commitFloat(event: Event): void {
    const target = event.currentTarget as HTMLInputElement;
    const parsed = Number.parseFloat(target.value);
    commitPrimitive(Number.isNaN(parsed) ? 0 : parsed);
  }

  function commitList(event: Event): void {
    const target = event.currentTarget as HTMLTextAreaElement;
    const items = target.value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
    listText = items.join('\n');
    commitPrimitive(items);
  }

  function commitText(event: Event): void {
    const target = event.currentTarget as HTMLInputElement | HTMLTextAreaElement;
    commitPrimitive(target.value);
  }

  function commitCheckbox(event: Event): void {
    const target = event.currentTarget as HTMLInputElement;
    commitPrimitive(target.checked);
  }

  function commitSelectValue(option: string): void {
    commitPrimitive(option);
  }

  function shouldUseTextarea(value: unknown): boolean {
    return typeof value === 'string' && (value.includes('\n') || value.length > 80);
  }

  function stringValue(current: FieldValue | null | undefined): string {
    if (typeof current === 'string') {
      return current;
    }
    return '';
  }
</script>

{#if field.type === 'group' && field.children}
  <fieldset class="field-group">
    <legend class:recommended={field.recommended}>{field.label}</legend>
    {#if field.description}
      <p class="field-description">{field.description}</p>
    {/if}
    <div class="field-group-children">
      {#each field.children as child (child.id)}
        <svelte:self
          field={child}
          {sectionId}
          path={[...pathTokens]}
          {updateField}
          {updateGroupField}
          parentGroup={field}
        />
      {/each}
    </div>
  </fieldset>
{:else}
  <div class="field-item" data-type={field.type}>
    <div class="field-header">
      <label id={labelElementId} for={elementId} class:recommended={field.recommended}>
        {field.label}
      </label>
      {#if field.description}
        <p id={descriptionId} class="field-description">{field.description}</p>
      {/if}
    </div>
    {#if field.type === 'boolean'}
      <label class="toggle-switch" for={elementId}>
        <input
          id={elementId}
          aria-describedby={field.description ? descriptionId : undefined}
          type="checkbox"
          checked={Boolean(field.value)}
          on:change={commitCheckbox}
        />
        <span class="toggle-slider"></span>
      </label>
    {:else if field.type === 'integer'}
      <input
        id={elementId}
        aria-describedby={field.description ? descriptionId : undefined}
        type="number"
        step="1"
        value={typeof field.value === 'number' ? field.value : ''}
        on:input={commitInteger}
      />
    {:else if field.type === 'float'}
      <input
        id={elementId}
        aria-describedby={field.description ? descriptionId : undefined}
        type="number"
        step="any"
        value={typeof field.value === 'number' ? field.value : ''}
        on:input={commitFloat}
      />
    {:else if field.type === 'select'}
      <SelectField
        id={elementId}
        labelId={field.label ? labelElementId : undefined}
        descriptionId={field.description ? descriptionId : undefined}
        options={field.choices ?? []}
        value={typeof field.value === 'string' ? field.value : ''}
        placeholder="選択してください"
        on:change={(event) => commitSelectValue(event.detail)}
      />
    {:else if field.type === 'list'}
      <textarea
        id={elementId}
        aria-describedby={field.description ? descriptionId : undefined}
        class="list-input"
        rows="6"
        value={listText}
        on:input={commitList}
      />
    {:else if field.type === 'password'}
      <div class="password-field">
        <input
          id={elementId}
          aria-describedby={field.description ? descriptionId : undefined}
          type={showPassword ? 'text' : 'password'}
          value={stringValue(field.value)}
          on:input={commitText}
          autocomplete="current-password"
        />
        <button
          type="button"
          class="password-toggle"
          on:click={() => (showPassword = !showPassword)}
          aria-label={showPassword ? 'パスワードを隠す' : 'パスワードを表示'}
        >
          {#if showPassword}
            <EyeOff size={18} />
          {:else}
            <Eye size={18} />
          {/if}
        </button>
      </div>
    {:else if shouldUseTextarea(field.value)}
      <textarea
        id={elementId}
        aria-describedby={field.description ? descriptionId : undefined}
        rows="4"
        value={stringValue(field.value)}
        on:input={commitText}
      />
    {:else}
      <input
        id={elementId}
        aria-describedby={field.description ? descriptionId : undefined}
        type="text"
        value={stringValue(field.value)}
        on:input={commitText}
      />
    {/if}
  </div>
{/if}

<style>
  .field-item {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    padding: 1.25rem;
    border-radius: 0.875rem;
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.05) 0%,
      rgba(255, 255, 255, 0.02) 100%
    );
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow:
      0 0.5rem 1.5rem rgba(0, 0, 0, 0.18),
      inset 0 1px 0 rgba(255, 255, 255, 0.08);
    transition:
      transform 0.25s ease,
      border-color 0.25s ease,
      box-shadow 0.25s ease;
    width: 100%;
    text-align: left;
  }

  .field-item:hover {
    transform: translateY(-0.125rem);
    border-color: rgba(25, 211, 199, 0.25);
    box-shadow:
      0 0.75rem 2rem rgba(25, 211, 199, 0.16),
      inset 0 1px 0 rgba(255, 255, 255, 0.12);
  }

  .field-header {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    width: 100%;
  }

  label {
    font-weight: 600;
    color: rgba(248, 250, 252, 0.92);
  }

  label.recommended {
    color: #38bdf8;
  }

  input[type='text'],
  input[type='password'],
  input[type='number'],
  textarea {
    width: 100%;
    background: linear-gradient(135deg, rgba(8, 11, 22, 0.65) 0%, rgba(12, 22, 32, 0.45) 100%);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 0.625rem;
    padding: 0.75rem 1rem;
    color: rgba(226, 232, 240, 0.95);
    font-size: 0.95rem;
    box-shadow:
      inset 0 1px 2px rgba(0, 0, 0, 0.4),
      0 1px 2px rgba(0, 0, 0, 0.2);
    transition:
      border-color 0.2s ease,
      box-shadow 0.2s ease,
      background 0.2s ease;
  }

  input[type='text']:focus,
  input[type='password']:focus,
  input[type='number']:focus,
  textarea:focus {
    outline: none;
    border-color: rgba(25, 211, 199, 0.55);
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.14) 0%, rgba(25, 211, 199, 0.06) 100%);
    box-shadow:
      0 0 0 0.1875rem rgba(25, 211, 199, 0.18),
      0 0.35rem 0.9rem rgba(25, 211, 199, 0.22);
  }

  input::placeholder,
  textarea::placeholder {
    color: rgba(148, 163, 184, 0.6);
  }

  input[type='checkbox'] {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .toggle-switch {
    position: relative;
    display: inline-block;
    width: 3.5rem;
    height: 2rem;
    cursor: pointer;
  }

  .toggle-slider {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      135deg,
      rgba(148, 163, 184, 0.28) 0%,
      rgba(100, 116, 139, 0.28) 100%
    );
    border: 1px solid rgba(148, 163, 184, 0.45);
    border-radius: 2rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow:
      inset 0 0.125rem 0.25rem rgba(0, 0, 0, 0.25),
      0 0.125rem 0.25rem rgba(0, 0, 0, 0.15);
  }

  .toggle-slider::before {
    content: '';
    position: absolute;
    height: 1.5rem;
    width: 1.5rem;
    left: 0.25rem;
    bottom: 0.25rem;
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.95) 0%,
      rgba(226, 232, 240, 0.9) 100%
    );
    border-radius: 50%;
    transition: inherit;
    box-shadow:
      0 0.25rem 0.5rem rgba(0, 0, 0, 0.35),
      0 0.125rem 0.25rem rgba(0, 0, 0, 0.25);
  }

  input[type='checkbox']:checked + .toggle-slider {
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.92) 0%, rgba(25, 211, 199, 0.78) 100%);
    border-color: rgba(25, 211, 199, 0.65);
    box-shadow:
      inset 0 0.125rem 0.35rem rgba(0, 0, 0, 0.15),
      0 0.5rem 1rem rgba(25, 211, 199, 0.28);
  }

  input[type='checkbox']:checked + .toggle-slider::before {
    transform: translateX(1.5rem);
    background: linear-gradient(135deg, rgba(255, 255, 255, 1) 0%, rgba(240, 253, 250, 0.96) 100%);
    box-shadow:
      0 0.3rem 0.6rem rgba(0, 0, 0, 0.28),
      0 0.125rem 0.5rem rgba(25, 211, 199, 0.4);
  }

  input[type='checkbox']:focus + .toggle-slider {
    outline: 0.125rem solid rgba(25, 211, 199, 0.55);
    outline-offset: 0.125rem;
  }

  .toggle-switch:hover .toggle-slider {
    border-color: rgba(25, 211, 199, 0.5);
    box-shadow:
      inset 0 0.125rem 0.35rem rgba(0, 0, 0, 0.22),
      0 0.25rem 0.75rem rgba(25, 211, 199, 0.24);
  }

  input[type='checkbox']:checked + .toggle-slider:hover {
    background: linear-gradient(135deg, rgba(25, 211, 199, 1) 0%, rgba(25, 211, 199, 0.86) 100%);
    box-shadow:
      inset 0 0.125rem 0.35rem rgba(0, 0, 0, 0.18),
      0 0.4rem 1.1rem rgba(25, 211, 199, 0.4);
  }

  textarea {
    resize: vertical;
    min-height: 3.5rem;
  }

  .list-input {
    min-height: 6rem;
  }

  .field-description {
    font-size: 0.85rem;
    color: rgba(226, 232, 240, 0.68);
    margin: 0;
  }

  .field-group {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 1rem;
    padding: 1.25rem;
    margin: 0;
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.05) 0%,
      rgba(255, 255, 255, 0.015) 100%
    );
    box-shadow:
      0 0.5rem 1.5rem rgba(0, 0, 0, 0.18),
      inset 0 1px 0 rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .field-group legend {
    padding: 0 0.75rem;
    font-weight: 600;
    color: rgba(248, 250, 252, 0.94);
  }

  .field-group legend.recommended {
    color: #38bdf8;
  }

  .field-group-children {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }

  .field-group .field-description {
    margin-top: 0;
  }

  .password-field {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
  }

  .password-field input {
    padding-right: 3rem;
  }

  .password-toggle {
    position: absolute;
    right: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.25rem;
    border: none;
    background: transparent;
    color: rgba(148, 163, 184, 0.7);
    cursor: pointer;
    transition: color 0.2s ease;
    border-radius: 0.375rem;
  }

  .password-toggle:hover {
    color: rgba(226, 232, 240, 0.95);
  }

  .password-toggle:focus {
    outline: none;
    color: rgba(25, 211, 199, 0.9);
  }
</style>
