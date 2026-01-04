<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';

  export let id: string;
  export let options: string[] = [];
  export let value = '';
  export let disabled = false;
  export let labelId: string | undefined;
  export let descriptionId: string | undefined;
  export let placeholder = '選択してください';

  const dispatch = createEventDispatcher<{ change: string }>();

  let isOpen = false;
  let highlightedIndex = -1;
  let buttonElement: HTMLButtonElement | null = null;
  let listboxElement: HTMLUListElement | null = null;
  let containerElement: HTMLDivElement | null = null;

  function setHighlightedIndexByValue(selected: string): void {
    const index = options.findIndex((option) => option === selected);
    highlightedIndex = index >= 0 ? index : options.length > 0 ? 0 : -1;
  }

  function setHighlightedIndex(index: number): void {
    if (options.length === 0) {
      highlightedIndex = -1;
      return;
    }
    const normalized = index < 0 ? options.length - 1 : index >= options.length ? 0 : index;
    highlightedIndex = normalized;
  }

  async function openDropdown(): Promise<void> {
    if (disabled || options.length === 0) {
      return;
    }
    isOpen = true;
    setHighlightedIndexByValue(value);
    await tick();
    listboxElement?.focus();
  }

  function closeDropdown(): void {
    if (!isOpen) {
      return;
    }
    isOpen = false;
    highlightedIndex = -1;
  }

  function toggleDropdown(): void {
    if (isOpen) {
      closeDropdown();
    } else {
      void openDropdown();
    }
  }

  function selectOption(option: string): void {
    if (disabled) {
      return;
    }
    dispatch('change', option);
    closeDropdown();
    buttonElement?.focus();
  }

  function handleButtonKeydown(event: KeyboardEvent): void {
    if (disabled) {
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      void openDropdown();
      if (event.key === 'ArrowDown' && options.length > 0) {
        setHighlightedIndexByValue(value);
      } else if (event.key === 'ArrowUp' && options.length > 0) {
        setHighlightedIndexByValue(value);
      }
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void openDropdown();
    }
  }

  function handleListboxKeydown(event: KeyboardEvent): void {
    if (!isOpen) {
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlightedIndex(highlightedIndex + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex(highlightedIndex - 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      setHighlightedIndex(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      setHighlightedIndex(options.length - 1);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < options.length) {
        selectOption(options[highlightedIndex]);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeDropdown();
      buttonElement?.focus();
    } else if (event.key === 'Tab') {
      closeDropdown();
    }
  }

  function handleOutsideClick(event: MouseEvent): void {
    if (!isOpen) {
      return;
    }
    const target = event.target as Node;
    if (containerElement && !containerElement.contains(target)) {
      closeDropdown();
    }
  }

  onMount(() => {
    document.addEventListener('mousedown', handleOutsideClick);
  });

  onDestroy(() => {
    document.removeEventListener('mousedown', handleOutsideClick);
  });

  $: displayValue = value && options.includes(value) ? value : (placeholder ?? options[0] ?? '');
</script>

<div class="select-container" bind:this={containerElement}>
  <button
    class="select-trigger"
    bind:this={buttonElement}
    type="button"
    {id}
    role="combobox"
    aria-haspopup="listbox"
    aria-expanded={isOpen}
    aria-controls={`${id}-listbox`}
    aria-labelledby={labelId}
    aria-describedby={descriptionId}
    on:click={toggleDropdown}
    on:keydown={handleButtonKeydown}
    disabled={disabled || options.length === 0}
  >
    <span class="select-value">{displayValue}</span>
    <span class="chevron" aria-hidden="true">▾</span>
  </button>
  {#if isOpen}
    <ul
      class="select-dropdown"
      role="listbox"
      id={`${id}-listbox`}
      bind:this={listboxElement}
      tabindex="-1"
      aria-labelledby={labelId}
      aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
      on:keydown={handleListboxKeydown}
    >
      {#each options as option, index}
        <li
          id={`${id}-option-${index}`}
          role="option"
          class:selected={option === value}
          class:highlighted={index === highlightedIndex}
          aria-selected={option === value}
          on:mousedown|preventDefault={() => selectOption(option)}
          on:mouseenter={() => setHighlightedIndex(index)}
        >
          <span>{option}</span>
          {#if option === value}
            <span class="checkmark" aria-hidden="true">✓</span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .select-container {
    position: relative;
    width: 100%;
  }

  .select-trigger {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    background: linear-gradient(135deg, rgba(8, 11, 22, 0.65) 0%, rgba(12, 22, 32, 0.45) 100%);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 0.625rem;
    padding: 0.75rem 1rem;
    color: rgba(226, 232, 240, 0.95);
    font-size: 0.95rem;
    font-weight: 500;
    box-shadow:
      inset 0 1px 2px rgba(0, 0, 0, 0.4),
      0 1px 2px rgba(0, 0, 0, 0.2);
    cursor: pointer;
    transition:
      border-color 0.25s ease,
      box-shadow 0.25s ease,
      background 0.25s ease,
      transform 0.25s ease;
  }

  .select-trigger:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .select-trigger:not(:disabled):hover,
  .select-trigger:not(:disabled):focus-visible {
    border-color: rgba(25, 211, 199, 0.55);
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.14) 0%, rgba(25, 211, 199, 0.06) 100%);
    box-shadow:
      0 0 0 0.1875rem rgba(25, 211, 199, 0.18),
      0 0.35rem 0.9rem rgba(25, 211, 199, 0.22);
    transform: translateY(-0.125rem);
    outline: none;
  }

  .select-value {
    flex: 1 1 auto;
    text-align: left;
  }

  .chevron {
    flex: 0 0 auto;
    font-size: 0.9rem;
    color: rgba(226, 232, 240, 0.7);
    transition:
      transform 0.2s ease,
      color 0.2s ease;
  }

  .select-trigger[aria-expanded='true'] .chevron {
    transform: rotate(180deg);
    color: #19d3c7;
  }

  .select-dropdown {
    position: absolute;
    top: calc(100% + 0.35rem);
    left: 0;
    right: 0;
    z-index: 20;
    margin: 0;
    padding: 0.35rem;
    list-style: none;
    background: linear-gradient(135deg, rgba(12, 20, 32, 0.95) 0%, rgba(6, 12, 22, 0.92) 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 0.75rem;
    box-shadow:
      0 1.25rem 3rem rgba(0, 0, 0, 0.45),
      0 0 0 1px rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(18px) saturate(180%);
    -webkit-backdrop-filter: blur(18px) saturate(180%);
    max-height: 14rem;
    overflow-y: auto;
    outline: none;
  }

  .select-dropdown li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.65rem 0.85rem;
    border-radius: 0.6rem;
    color: rgba(226, 232, 240, 0.9);
    cursor: pointer;
    transition:
      background 0.2s ease,
      color 0.2s ease,
      transform 0.2s ease,
      box-shadow 0.2s ease;
  }

  .select-dropdown li.highlighted {
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.24) 0%, rgba(25, 211, 199, 0.12) 100%);
    color: #041b1a;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.2),
      0 6px 16px rgba(25, 211, 199, 0.18);
    transform: translateX(0.1rem);
  }

  .select-dropdown li.selected {
    color: #19d3c7;
  }

  .checkmark {
    font-size: 0.85rem;
  }

  .select-dropdown::-webkit-scrollbar {
    width: 0.4rem;
  }

  .select-dropdown::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 999px;
  }

  .select-dropdown::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, rgba(25, 211, 199, 0.6) 0%, rgba(25, 211, 199, 0.4) 100%);
    border-radius: 999px;
  }
</style>
