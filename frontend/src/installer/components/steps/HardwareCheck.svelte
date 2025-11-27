<script lang="ts">
  import { Check, Gamepad, Cpu, HardDrive, Wifi, Cable } from "lucide-svelte";
  import { markSubstepCompleted, installationState } from "../../store";
  import { InstallationStep } from "../../types";

  const SUBSTEP_STORAGE_KEY = "hardware_substep_index";

  interface HardwareRequirement {
    id: string;
    name: string;
    spec: string;
    icon: any;
    checked: boolean;
    isConnection?: boolean;
  }

  let requirements: HardwareRequirement[] = [
    {
      id: "hardware-switch",
      name: "Nintendo Switch",
      spec: "スプラトゥーン 3 をプレイする本体",
      icon: Gamepad,
      checked: false,
    },
    {
      id: "hardware-capture",
      name: "キャプチャーボード",
      spec: "HDMI 入力対応、1080p/30fps 以上推奨",
      icon: Cpu,
      checked: false,
    },
    {
      id: "hardware-pc",
      name: "PC",
      spec: "Windows 11、メモリ 8GB 以上、ストレージ 10GB 以上の空き容量",
      icon: HardDrive,
      checked: false,
    },
    {
      id: "hardware-network",
      name: "ネットワーク",
      spec: "YouTube アップロード用の安定したインターネット接続",
      icon: Wifi,
      checked: false,
    },
    {
      id: "hardware-connection",
      name: "接続",
      spec: "Nintendo Switchの電源を入れ、以下のように接続してください",
      icon: Cable,
      checked: false,
      isConnection: true,
    },
  ];

  let currentSubStepIndex = 0;
  let hasInitializedSubstep = false;

  // 親コンポーネントに通知するためのフラグ
  export let canGoBack = false;
  export let isStepCompleted = false;

  $: isStepCompleted = requirements[currentSubStepIndex].checked;

  $: canGoBack = currentSubStepIndex > 0;

  function loadSavedSubstepIndex(maxIndex: number): number | null {
    if (typeof window === "undefined") return null;
    const stored = window.sessionStorage.getItem(SUBSTEP_STORAGE_KEY);
    if (stored === null) return null;
    const parsed = Number.parseInt(stored, 10);
    if (Number.isNaN(parsed)) return null;
    return Math.max(0, Math.min(parsed, maxIndex));
  }

  function saveSubstepIndex(index: number): void {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(SUBSTEP_STORAGE_KEY, index.toString());
  }

  function computeInitialSubstepIndex(steps: HardwareRequirement[]): number {
    const firstIncomplete = steps.findIndex((step) => !step.checked);
    if (firstIncomplete !== -1) {
      return firstIncomplete;
    }
    return steps.length > 0 ? steps.length - 1 : 0;
  }

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.HARDWARE_CHECK] || {};
    const updatedRequirements = requirements.map((req) => ({
      ...req,
      checked: details[req.id] || false,
    }));
    requirements = updatedRequirements;

    if (!hasInitializedSubstep) {
      const savedIndex = loadSavedSubstepIndex(updatedRequirements.length - 1);
      if (savedIndex !== null) {
        currentSubStepIndex = savedIndex;
      } else {
        currentSubStepIndex = computeInitialSubstepIndex(updatedRequirements);
      }
      hasInitializedSubstep = true;
    }
  }

  $: if (hasInitializedSubstep) {
    saveSubstepIndex(currentSubStepIndex);
  }

  export async function next(
    options: { skip?: boolean } = {},
  ): Promise<boolean> {
    // 現在のステップをチェック済みにする
    if (!options.skip && !requirements[currentSubStepIndex].checked) {
      await toggleRequirement(currentSubStepIndex);
    }

    if (currentSubStepIndex < requirements.length - 1) {
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

  async function toggleRequirement(index: number): Promise<void> {
    const req = requirements[index];
    const updatedChecked = !req.checked;

    requirements = requirements.map((requirement, requirementIndex) =>
      requirementIndex === index
        ? { ...requirement, checked: updatedChecked }
        : requirement,
    );

    await markSubstepCompleted(
      InstallationStep.HARDWARE_CHECK,
      req.id,
      updatedChecked,
    );
  }

  function handleCardClick(event: Event) {
    // テキスト選択中は反応しない
    if (window.getSelection()?.toString()) {
      return;
    }

    // イベントターゲットの取得と要素への正規化（テキストノードの場合は親要素を取得）
    let target = event.target as Element;
    if (target.nodeType === Node.TEXT_NODE) {
      target = target.parentElement as Element;
    }

    // インタラクティブな要素のクリックは除外
    if (
      target &&
      (target.closest("button") ||
        target.closest("a") ||
        target.closest("input"))
    ) {
      return;
    }

    toggleRequirement(currentSubStepIndex);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      handleCardClick(event);
    }
  }
</script>

<div class="hardware-check">
  <div class="step-header">
    <h2 class="step-title">準備するもの</h2>
    <p class="step-description">
      Splat Replay を使用するために以下のものを準備します
    </p>
  </div>

  <div class="requirements-section">
    <div
      class="requirement-card glass-card"
      class:completed={requirements[currentSubStepIndex].checked}
      on:click={handleCardClick}
      on:keydown={handleKeyDown}
      role="button"
      tabindex="0"
    >
      {#key currentSubStepIndex}
        <div class="requirement-content-wrapper">
          <div class="card-header">
            <div class="header-left">
              <div class="requirement-icon-large">
                <svelte:component
                  this={requirements[currentSubStepIndex].icon}
                  class="icon"
                  size={32}
                  stroke-width={1.5}
                />
              </div>
              <h3 class="requirement-name-large">
                {requirements[currentSubStepIndex].name}
              </h3>
            </div>
            <div
              class="checkbox-indicator"
              class:checked={requirements[currentSubStepIndex].checked}
            >
              {#if requirements[currentSubStepIndex].checked}
                <Check size={20} />
              {/if}
            </div>
          </div>

          <div class="card-body">
            <p class="requirement-spec-large">
              {requirements[currentSubStepIndex].spec}
            </p>

            {#if requirements[currentSubStepIndex].isConnection}
              <div class="diagram-content">
                <div class="diagram-item">
                  <div class="diagram-box switch">Switch</div>
                  <div class="diagram-arrow">→</div>
                </div>
                <div class="diagram-item">
                  <div class="diagram-box capture">キャプボ</div>
                  <div class="diagram-arrow">→</div>
                </div>
                <div class="diagram-item">
                  <div class="diagram-box pc">PC</div>
                </div>
              </div>
            {/if}
          </div>
        </div>
      {/key}
    </div>
  </div>
</div>

<style>
  .hardware-check {
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

  .requirements-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 0;
  }

  .requirement-card {
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

  .requirement-card:focus-visible {
    box-shadow: 0 0 0 2px var(--accent-color);
  }

  .requirement-card:hover {
    border-color: rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.05);
  }

  .requirement-card.completed {
    border-color: var(--accent-color);
    box-shadow: 0 0 15px rgba(25, 211, 199, 0.1);
    background: rgba(25, 211, 199, 0.05);
  }

  .requirement-content-wrapper {
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

  .requirement-icon-large {
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: linear-gradient(
      135deg,
      rgba(25, 211, 199, 0.2) 0%,
      rgba(25, 211, 199, 0.05) 100%
    );
    border: 1px solid rgba(25, 211, 199, 0.3);
    color: var(--accent-color);
  }

  .requirement-name-large {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    text-align: left;
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

  .requirement-spec-large {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  .diagram-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin: 1rem 0;
    width: 100%;
  }

  .diagram-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .diagram-box {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.875rem;
    text-align: center;
    min-width: 80px;
    border: 2px solid;
  }

  .diagram-box.switch {
    background: rgba(255, 69, 58, 0.1);
    border-color: rgba(255, 69, 58, 0.5);
    color: #ff453a;
  }

  .diagram-box.capture {
    background: rgba(255, 159, 10, 0.1);
    border-color: rgba(255, 159, 10, 0.5);
    color: #ff9f0a;
  }

  .diagram-box.pc {
    background: rgba(25, 211, 199, 0.1);
    border-color: rgba(25, 211, 199, 0.5);
    color: var(--accent-color);
  }

  .diagram-arrow {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-secondary);
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

  .requirement-card:hover .checkbox-indicator:not(.checked) {
    border-color: rgba(255, 255, 255, 0.4);
    background: rgba(255, 255, 255, 0.1);
  }

  @media (max-width: 768px) {
    .requirement-card {
      padding: 1.5rem;
    }

    .requirement-name-large {
      font-size: 1.25rem;
    }

    .diagram-content {
      flex-direction: column;
    }

    .diagram-arrow {
      transform: rotate(90deg);
    }
  }

  @media (max-height: 700px) {
    .requirement-card {
      padding: 1rem;
    }
  }
</style>
