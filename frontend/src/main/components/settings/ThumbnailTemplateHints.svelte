<script lang="ts">
  import { tick } from 'svelte';
  import { Copy, Check } from 'lucide-svelte';
  let { variables }: { variables: Record<string, string | number> } = $props();
  const labels: Record<string, string> = {
    WIN: '勝数',
    LOSE: '敗数',
    RATE: 'レート（ラベル付き）',
    RATE_LABEL: 'レートのラベル',
    RATE_VALUE: 'レートの値',
    RATE_MIN: '最小レート',
    RATE_MAX: '最大レート',
    BATTLE: 'マッチ名',
    RULE: 'ルール名',
    STAGES: 'ステージ名',
  };
  let copied = $state('');
  let message = $state('');
  let fallback = $state('');
  let fallbackInput = $state<HTMLInputElement>();
  async function copy(key: string): Promise<void> {
    const token = `{${key}}`;
    message = '';
    copied = '';
    fallback = '';
    try {
      await navigator.clipboard.writeText(token);
      copied = key;
      message = `${token}をコピーしました`;
    } catch {
      fallback = token;
      message = 'コピーできませんでした。下の変数を選択してコピーしてください。';
      await tick();
      fallbackInput?.focus();
      fallbackInput?.select();
    }
  }
</script>

<details class="template-hints">
  <summary>使えるテンプレート変数</summary>
  <p class="feedback" role="status">{message}</p>
  {#if fallback}<input
      bind:this={fallbackInput}
      aria-label="コピーする変数"
      value={fallback}
      readonly
    />{/if}
  <p class="intro">変数をコピーして、入力欄へ貼り付けられます。</p>
  <div class="variable-list">
    {#each Object.entries(variables) as [key, example]}
      <div class="variable">
        <button
          type="button"
          aria-label={`{${key}}をコピー`}
          title="変数をコピー"
          onclick={() => void copy(key)}
          ><code>{`{${key}}`}</code>{#if copied === key}<Check size={13} />{:else}<Copy
              size={13}
            />{/if}</button
        ><span>{labels[key] ?? key}<small>例：{example}</small></span>
      </div>
    {/each}
  </div>
</details>

<style>
  .template-hints {
    font-size: 0.75rem;
    text-align: left;
  }
  summary {
    color: var(--text-secondary);
    cursor: pointer;
    width: fit-content;
    padding: 0.1rem 0;
  }
  summary:hover {
    color: var(--theme-accent-color);
  }
  summary:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 3px;
  }
  .intro,
  .feedback {
    text-align: left;
    font-size: 0.72rem;
    line-height: 1.5;
    color: var(--text-secondary);
    margin: 0.6rem 0;
  }
  .feedback:empty {
    display: none;
  }
  .variable-list {
    display: grid;
    gap: 0.45rem;
  }
  .variable {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.6rem;
    align-items: center;
  }
  .variable small {
    display: block;
    opacity: 0.8;
    margin-top: 0.1rem;
    font-size: 0.68rem;
  }
  .variable span {
    color: var(--text-secondary);
    font-size: 0.72rem;
    overflow-wrap: anywhere;
  }
  button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    font: inherit;
    font-size: 0.75rem;
    padding: 0.3rem 0.45rem;
    color: var(--text-primary);
    border: 1px solid var(--glass-border);
    border-radius: 0.25rem;
    background: transparent;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    cursor: pointer;
    transform: none;
  }
  button:hover {
    background: rgba(var(--theme-rgb-accent), 0.08);
    transform: none;
  }
  button:active {
    transform: none;
  }
  button:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 2px;
  }
  code {
    user-select: all;
    font-size: 0.73rem;
  }
  input {
    box-sizing: border-box;
    width: 100%;
    font: inherit;
    padding: 0.4rem;
    border: 1px solid var(--glass-border);
    color: var(--text-primary);
    background: var(--glass-bg-strong);
    border-radius: 0.25rem;
  }
</style>
