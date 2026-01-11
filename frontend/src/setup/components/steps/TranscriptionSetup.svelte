<script lang="ts">
  import { onMount } from 'svelte';
  import { Check, ExternalLink, RefreshCw, Eye, EyeOff } from 'lucide-svelte';
  import { markSubstepCompleted } from '../../stores/navigation';
  import { setupState } from '../../stores/state';
  import {
    getTranscriptionConfig,
    listMicrophones,
    saveTranscriptionConfig,
    type TranscriptionConfig,
  } from '../../stores/config';
  import { SetupStep } from '../../types';
  import NotificationDialog from '../../../common/components/NotificationDialog.svelte';

  const SUBSTEP_STORAGE_KEY = 'transcription_substep_index';

  interface SetupStepItem {
    id: string;
    title: string;
    description: string;
    completed: boolean;
  }

  let setupSteps: SetupStepItem[] = [
    {
      id: 'transcription-enable',
      title: '文字起こしの使用選択',
      description: '文字起こし機能を使用するか選びます。',
      completed: false,
    },
    {
      id: 'transcription-mic',
      title: 'マイク名の入力',
      description: 'OSが認識しているマイクの名称を入力します。',
      completed: false,
    },
    {
      id: 'transcription-groq',
      title: 'Groq API キーの入力',
      description: 'Groq API キーを入力して文字起こしを有効化します。',
      completed: false,
    },
    {
      id: 'transcription-dictionary',
      title: 'カスタム辞書の設定',
      description: '認識しやすくしたい単語を1行ずつ入力します。',
      completed: false,
    },
  ];

  let currentSubStepIndex = 0;
  let hasInitializedSubstep = false;
  let isSaving = false;
  let dialogOpen = false;
  let dialogMessage = '';
  let dialogVariant: 'info' | 'success' | 'warning' | 'error' = 'info';

  let micDeviceName = '';
  let groqApiKey = '';
  let showApiKey = false;
  let language = 'ja-JP';
  let customDictionaryText = '';
  let microphoneDevices: string[] = [];
  let isLoadingMicrophones = false;
  let useTranscription: boolean | null = null;
  let hasLoadedMicrophones = false;

  export let canGoBack = false;
  export let isStepCompleted = false;

  let currentStepCompleted = false;
  $: {
    if (currentSubStepIndex === 0) {
      currentStepCompleted = useTranscription !== null;
    } else {
      currentStepCompleted = setupSteps[currentSubStepIndex]?.completed || false;
    }
    isStepCompleted = currentStepCompleted;
  }
  $: canGoBack = currentSubStepIndex > 0;

  onMount(async () => {
    await loadConfig();
    if (useTranscription) {
      await loadMicrophones();
    }
  });

  function loadSavedSubstepIndex(maxIndex: number): number | null {
    if (typeof window === 'undefined') return null;
    const stored = window.sessionStorage.getItem(SUBSTEP_STORAGE_KEY);
    if (stored === null) return null;
    const parsed = Number.parseInt(stored, 10);
    if (Number.isNaN(parsed)) return null;
    return Math.max(0, Math.min(parsed, maxIndex));
  }

  function saveSubstepIndex(index: number): void {
    if (typeof window === 'undefined') return;
    window.sessionStorage.setItem(SUBSTEP_STORAGE_KEY, index.toString());
  }

  function computeInitialSubstepIndex(_steps: SetupStepItem[]): number {
    return 0;
  }

  $: if ($setupState?.current_step !== SetupStep.TRANSCRIPTION_SETUP) {
    hasInitializedSubstep = false;
  }

  $: if ($setupState && $setupState.step_details) {
    const details = $setupState.step_details[SetupStep.TRANSCRIPTION_SETUP] || {};
    const updatedSteps = setupSteps.map((step) => ({
      ...step,
      completed: details[step.id] || false,
    }));
    setupSteps = updatedSteps;

    if (!hasInitializedSubstep && $setupState.current_step === SetupStep.TRANSCRIPTION_SETUP) {
      const savedIndex = loadSavedSubstepIndex(updatedSteps.length - 1);
      if (savedIndex !== null) {
        currentSubStepIndex = savedIndex;
      } else {
        currentSubStepIndex = computeInitialSubstepIndex(updatedSteps);
      }
      hasInitializedSubstep = true;
    }
  }

  $: if (hasInitializedSubstep) {
    saveSubstepIndex(currentSubStepIndex);
  }

  export async function next(options: { skip?: boolean } = {}): Promise<boolean> {
    const currentStep = setupSteps[currentSubStepIndex];

    if (currentSubStepIndex === 0 && useTranscription === null) {
      showDialog('文字起こしを使用するか選択してください。', 'warning');
      return true;
    }

    if (currentSubStepIndex === 0 && useTranscription === false) {
      const saved = await saveCurrentConfig();
      if (!saved) {
        return true;
      }
      return false;
    }

    if (!options.skip) {
      const validationError = validateCurrentStep(currentSubStepIndex);
      if (validationError) {
        showDialog(validationError, 'warning');
        return true;
      }

      const saved = await saveCurrentConfig();
      if (!saved) {
        return true;
      }

      await markSubstepCompleted(SetupStep.TRANSCRIPTION_SETUP, currentStep.id, true);
    }

    if (currentSubStepIndex < setupSteps.length - 1) {
      currentSubStepIndex++;
      return true;
    }
    return false;
  }

  export async function back(): Promise<boolean> {
    if (currentSubStepIndex > 0) {
      currentSubStepIndex--;
      return true;
    }
    return false;
  }

  async function toggleStep(index: number): Promise<void> {
    const step = setupSteps[index];

    if (step.completed) {
      await markSubstepCompleted(SetupStep.TRANSCRIPTION_SETUP, step.id, false);
      return;
    }

    const validationError = validateCurrentStep(index);
    if (validationError) {
      showDialog(validationError, 'warning');
      return;
    }

    const saved = await saveCurrentConfig();
    if (!saved) {
      return;
    }

    await markSubstepCompleted(SetupStep.TRANSCRIPTION_SETUP, step.id, true);
  }

  function handleCardClick(event: Event) {
    if (isSaving) return;
    if (currentSubStepIndex === 0) return;

    if (window.getSelection()?.toString()) {
      return;
    }

    let target = event.target as Element;
    if (target.nodeType === Node.TEXT_NODE) {
      target = target.parentElement as Element;
    }

    if (
      target &&
      (target.closest('button') ||
        target.closest('a') ||
        target.closest('input') ||
        target.closest('textarea'))
    ) {
      return;
    }

    toggleStep(currentSubStepIndex);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      handleCardClick(event);
    }
  }

  function parseDictionary(text: string): string[] {
    return text
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }

  function buildConfig(): TranscriptionConfig {
    if (useTranscription === false) {
      return {
        enabled: false,
        micDeviceName: micDeviceName.trim(),
        groqApiKey: groqApiKey.trim(),
        language: language.trim(),
        customDictionary: parseDictionary(customDictionaryText),
      };
    }
    return {
      enabled: true,
      micDeviceName: micDeviceName.trim(),
      groqApiKey: groqApiKey.trim(),
      language: language.trim(),
      customDictionary: parseDictionary(customDictionaryText),
    };
  }

  function validateCurrentStep(stepIndex: number): string | null {
    if (stepIndex === 0 && useTranscription === null) {
      return '文字起こしを使用するか選択してください。';
    }
    if (stepIndex === 1 && micDeviceName.trim().length === 0) {
      return 'マイク名を入力してください。';
    }
    if (stepIndex === 2 && groqApiKey.trim().length === 0) {
      return 'Groq API キーを入力してください。';
    }
    return null;
  }

  async function loadConfig(): Promise<void> {
    try {
      const config = await getTranscriptionConfig();
      micDeviceName = config.micDeviceName;
      groqApiKey = config.groqApiKey;
      language = config.language || 'ja-JP';
      customDictionaryText = config.customDictionary.join('\n');
      useTranscription = config.enabled;
    } catch (error) {
      console.error('Failed to load transcription config:', error);
      showDialog('文字起こし設定の取得に失敗しました。', 'error');
    }
  }

  async function loadMicrophones(): Promise<void> {
    isLoadingMicrophones = true;
    try {
      const devices = await listMicrophones();
      const normalizedDevices = Array.from(
        new Set(devices.map((device) => device.trim()).filter((device) => device.length > 0))
      );
      microphoneDevices = normalizedDevices;
      if (micDeviceName && !microphoneDevices.includes(micDeviceName)) {
        microphoneDevices = [...microphoneDevices, micDeviceName];
      }
      hasLoadedMicrophones = true;
    } catch (error) {
      console.error('Failed to load microphones:', error);
      showDialog('マイク一覧の取得に失敗しました。', 'error');
    } finally {
      isLoadingMicrophones = false;
    }
  }

  async function refreshMicrophones(event: Event): Promise<void> {
    event.stopPropagation();
    await loadMicrophones();
  }

  async function setTranscriptionUsage(value: boolean): Promise<void> {
    useTranscription = value;
    if (value && !hasLoadedMicrophones) {
      await loadMicrophones();
    }
    await markSubstepCompleted(SetupStep.TRANSCRIPTION_SETUP, setupSteps[0].id, true);
  }

  async function saveCurrentConfig(): Promise<boolean> {
    isSaving = true;
    try {
      await saveTranscriptionConfig(buildConfig());
      return true;
    } catch (error) {
      console.error('Failed to save transcription config:', error);
      showDialog('文字起こし設定の保存に失敗しました。', 'error');
      return false;
    } finally {
      isSaving = false;
    }
  }

  function showDialog(
    message: string,
    variant: 'info' | 'success' | 'warning' | 'error' = 'info'
  ): void {
    dialogMessage = message;
    dialogVariant = variant;
    dialogOpen = true;
  }
</script>

<div class="transcription-setup">
  <div class="step-header">
    <h2 class="step-title">文字起こしの設定</h2>
    <p class="step-description">マイクとGroq APIを使った文字起こしの設定を行います</p>
  </div>

  <div class="setup-steps-section">
    <div
      class="step-card glass-card"
      class:completed={currentStepCompleted}
      class:disabled={isSaving}
      on:click={handleCardClick}
      on:keydown={handleKeyDown}
      role="button"
      tabindex="0"
    >
      {#key currentSubStepIndex}
        <div class="step-content-wrapper">
          <div class="card-header">
            <div class="header-left">
              <div class="step-number-large">{currentSubStepIndex + 1}</div>
              <div class="title-wrapper">
                <h3 class="step-name-large">{setupSteps[currentSubStepIndex].title}</h3>
              </div>
            </div>
            <div class="checkbox-indicator" class:checked={currentStepCompleted}>
              {#if currentStepCompleted}
                <Check size={20} />
              {/if}
            </div>
          </div>

          <div class="card-body">
            {#if currentSubStepIndex === 0}
              <ol class="instruction-list">
                <li>
                  文字起こしを使用するか選択してください。
                  <div class="choice-group">
                    <button
                      type="button"
                      class="choice-button"
                      class:active={useTranscription === true}
                      aria-pressed={useTranscription === true}
                      on:click={() => setTranscriptionUsage(true)}
                    >
                      使用する
                    </button>
                    <button
                      type="button"
                      class="choice-button"
                      class:active={useTranscription === false}
                      aria-pressed={useTranscription === false}
                      on:click={() => setTranscriptionUsage(false)}
                    >
                      使用しない
                    </button>
                  </div>
                </li>
              </ol>
              <div class="instruction-block">
                <p class="instruction-text">
                  録画中に話した内容を文字起こしし、字幕として動画に追加します。
                </p>
                <p class="instruction-text">後から設定変更も可能です。</p>
              </div>
            {:else if currentSubStepIndex === 1}
              <ol class="instruction-list">
                <li>
                  音声認識に使用するマイクを一覧から選択してください。
                  <div class="input-row">
                    <select
                      class="device-select"
                      bind:value={micDeviceName}
                      on:click={(e) => e.stopPropagation()}
                      disabled={isLoadingMicrophones}
                    >
                      <option value="">-- マイクを選択 --</option>
                      {#each microphoneDevices as device}
                        <option value={device}>{device}</option>
                      {/each}
                    </select>
                    <button
                      class="refresh-button"
                      type="button"
                      on:click={refreshMicrophones}
                      disabled={isLoadingMicrophones}
                      title="マイク一覧を更新"
                    >
                      <RefreshCw class="icon" size={16} />
                    </button>
                  </div>
                </li>
                {#if !microphoneDevices.length}
                  <li>一覧が取得できない場合は、OS の設定でマイク接続を確認してください。</li>
                {/if}
              </ol>
            {:else if currentSubStepIndex === 2}
              <ol class="instruction-list">
                <li>
                  Groq のログインページにアクセスします。
                  <div style="margin-top: 1rem;">
                    <a
                      class="link-button"
                      href="https://console.groq.com/login"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink class="icon" size={16} />
                      Groq にログイン
                    </a>
                  </div>
                </li>
                <li>アカウント登録またはログインを完了します。</li>
                <li>
                  API Key の管理ページを開きます。
                  <div style="margin-top: 1rem;">
                    <a
                      class="link-button"
                      href="https://console.groq.com/keys"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink class="icon" size={16} />
                      API Key を作成する
                    </a>
                  </div>
                </li>
                <li>「Create API Key」をクリックしてキーを作成します。</li>
                <li>
                  発行したキーを入力します。
                  <div class="input-block">
                    <div class="password-field">
                      <input
                        class="text-input"
                        type={showApiKey ? 'text' : 'password'}
                        placeholder="gsk_..."
                        value={groqApiKey}
                        on:input={(e) => (groqApiKey = e.currentTarget.value)}
                        on:click={(e) => e.stopPropagation()}
                      />
                      <button
                        type="button"
                        class="password-toggle"
                        on:click={(e) => {
                          e.stopPropagation();
                          showApiKey = !showApiKey;
                        }}
                        aria-label={showApiKey ? 'APIキーを隠す' : 'APIキーを表示'}
                      >
                        {#if showApiKey}
                          <EyeOff size={18} />
                        {:else}
                          <Eye size={18} />
                        {/if}
                      </button>
                    </div>
                  </div>
                </li>
              </ol>
            {:else if currentSubStepIndex === 3}
              <ol class="instruction-list">
                <li>
                  認識させたい単語を 1 行につき 1 単語で入力します。
                  <div class="input-block">
                    <textarea
                      class="text-area"
                      rows="6"
                      placeholder="例:\nナイス\nキル\nデス"
                      bind:value={customDictionaryText}
                      on:click={(e) => e.stopPropagation()}
                    />
                  </div>
                </li>
              </ol>
              <div class="instruction-block">
                <p class="instruction-text">後から設定変更も可能です。</p>
              </div>
            {/if}
          </div>
        </div>
      {/key}
    </div>
  </div>
</div>

<NotificationDialog
  bind:isOpen={dialogOpen}
  variant={dialogVariant}
  message={dialogMessage}
  on:close={() => (dialogOpen = false)}
/>

<style>
  .transcription-setup {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 0;
    height: 100%;
    justify-content: center;
  }

  .step-header {
    text-align: center;
    margin-bottom: 1rem;
  }

  .step-title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .step-description {
    margin: 0.5rem 0 0 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }

  .setup-steps-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 0;
  }

  .step-card {
    width: 100%;
    max-width: 600px;
    height: 100%;
    padding: 2rem;
    display: flex;
    flex-direction: column;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    max-height: 100%;
    box-sizing: border-box;
    cursor: pointer;
    transition: all 0.2s ease;
    outline: none;
  }

  .step-card:focus-visible {
    box-shadow: 0 0 0 2px var(--accent-color);
  }

  .step-card:hover {
    border-color: rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.05);
  }

  .step-card.completed {
    border-color: var(--accent-color);
    box-shadow: 0 0 15px rgba(25, 211, 199, 0.1);
    background: rgba(25, 211, 199, 0.05);
  }

  .step-card.disabled {
    cursor: default;
    opacity: 0.8;
  }

  .step-card.disabled:hover {
    border-color: rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.03);
  }

  .step-content-wrapper {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    width: 100%;
    animation: fadeIn 0.3s ease-out;
    overflow: hidden;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .step-number-large {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(25, 211, 199, 0.2) 0%, rgba(25, 211, 199, 0.05) 100%);
    border: 2px solid rgba(25, 211, 199, 0.3);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent-color);
    flex-shrink: 0;
  }

  .title-wrapper {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }

  .step-name-large {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-primary);
    text-align: left;
  }

  .checkbox-indicator {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: transparent;
    transition: all 0.2s ease;
    background: rgba(255, 255, 255, 0.05);
  }

  .checkbox-indicator.checked {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #1a1a1a;
    box-shadow: 0 0 10px var(--accent-glow);
  }

  .step-card:hover .checkbox-indicator:not(.checked) {
    border-color: rgba(255, 255, 255, 0.4);
    background: rgba(255, 255, 255, 0.1);
  }

  .card-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    text-align: left;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
    padding-right: 0.5rem;
    box-sizing: border-box;
  }

  .card-body::-webkit-scrollbar {
    width: 8px;
  }

  .card-body::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
  }

  .card-body::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }

  .card-body::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  .instruction-list {
    margin: 0;
    padding-left: 1.25rem;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-secondary);
    overflow-wrap: anywhere;
  }

  .instruction-list li + li {
    margin-top: 0.5rem;
  }

  .instruction-block {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    color: var(--text-secondary);
  }

  .instruction-text {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
  }

  .choice-group {
    margin-top: 1rem;
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .choice-button {
    padding: 0.65rem 1.5rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .choice-button:hover {
    border-color: rgba(255, 255, 255, 0.4);
    color: var(--text-primary);
  }

  .choice-button.active {
    background: rgba(25, 211, 199, 0.15);
    border-color: var(--accent-color);
    color: var(--text-primary);
    box-shadow: 0 0 12px rgba(25, 211, 199, 0.2);
  }

  .link-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-secondary);
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s ease;
  }

  .link-button:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
  }

  .input-row {
    margin-top: 1rem;
    display: flex;
    gap: 0.5rem;
    align-items: center;
    width: 100%;
    flex-wrap: wrap;
    min-width: 0;
  }

  .input-row > * {
    min-width: 0;
  }

  .input-block {
    margin-top: 1rem;
    width: 100%;
  }

  .text-input,
  .text-area {
    width: 100%;
    max-width: 100%;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    font-family: inherit;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    transition: all 0.2s ease;
    box-sizing: border-box;
  }

  .device-select {
    flex: 1 1 0;
    min-width: 0;
    max-width: 100%;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    font-family: inherit;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background-color: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    transition: all 0.2s ease;
    box-sizing: border-box;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%2319D3C7' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 1rem center;
    background-size: 1.2em;
    padding-right: 2.5rem;
  }

  .device-select:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.3);
  }

  .device-select:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px rgba(25, 211, 199, 0.2);
    background-color: rgba(255, 255, 255, 0.1);
  }

  .device-select option {
    background-color: #1a1a1a;
    color: var(--text-primary);
    padding: 0.5rem;
  }

  .refresh-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 42px;
    height: 42px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }

  .refresh-button:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.3);
    color: var(--text-primary);
  }

  .refresh-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .text-input:focus,
  .text-area:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px rgba(25, 211, 199, 0.2);
    background: rgba(255, 255, 255, 0.1);
  }

  .text-area {
    resize: vertical;
    min-height: 140px;
  }

  @media (max-width: 768px) {
    .step-card {
      padding: 1.5rem;
    }

    .step-name-large {
      font-size: 1.125rem;
    }
  }

  @media (max-height: 700px) {
    .step-card {
      padding: 1rem;
    }
  }

  .password-field {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
  }

  .password-field :global(.text-input) {
    padding-right: 3rem !important;
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
    color: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    transition: color 0.2s ease;
    border-radius: 0.375rem;
    z-index: 5;
  }

  .password-toggle:hover {
    color: var(--text-primary);
  }

  .password-toggle:focus {
    outline: none;
    color: var(--accent-color);
  }
</style>
