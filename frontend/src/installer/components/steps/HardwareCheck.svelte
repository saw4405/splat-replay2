<script lang="ts">
  import { Check, Gamepad, Cpu, HardDrive, Wifi, Cable } from "lucide-svelte";
  import { markSubstepCompleted, installationState } from "../../store";
  import { InstallationStep } from "../../types";

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

  let allChecked = false;

  $: allChecked = requirements.every((req) => req.checked);

  // Sync with installation state
  $: if ($installationState && $installationState.step_details) {
    const details =
      $installationState.step_details[InstallationStep.HARDWARE_CHECK] || {};
    requirements = requirements.map((req) => ({
      ...req,
      checked: details[req.id] || false,
    }));
  }

  async function toggleRequirement(index: number): Promise<void> {
    const req = requirements[index];
    await markSubstepCompleted(
      InstallationStep.HARDWARE_CHECK,
      req.id,
      !req.checked,
    );
  }
</script>

<div class="hardware-check">
  <div class="step-header">
    <h2 class="step-title">準備するもの</h2>
    <p class="step-description">
      Splat Replay を使用するために以下のものを準備してください。
    </p>
  </div>

  <div class="requirements-section">
    <div class="requirements-list">
      {#each requirements as requirement, index}
        <div class="requirement-card glass-card">
          <button
            class="requirement-button"
            type="button"
            on:click={() => toggleRequirement(index)}
            aria-pressed={requirement.checked}
          >
            <div class="requirement-icon">
              <svelte:component
                this={requirement.icon}
                class="icon"
                size={32}
                stroke-width={1.5}
              />
            </div>
            <div class="requirement-content">
              <h4 class="requirement-name">{requirement.name}</h4>
              <p class="requirement-spec">{requirement.spec}</p>
              {#if requirement.isConnection}
                <div class="diagram-content">
                  <div class="diagram-item">
                    <div class="diagram-box switch">Nintendo Switch</div>
                    <div class="diagram-arrow">HDMI →</div>
                  </div>
                  <div class="diagram-item">
                    <div class="diagram-box capture">キャプチャーボード</div>
                    <div class="diagram-arrow">USB →</div>
                  </div>
                  <div class="diagram-item">
                    <div class="diagram-box pc">PC</div>
                  </div>
                </div>
              {/if}
            </div>
            <div
              class="requirement-checkbox"
              class:checked={requirement.checked}
            >
              {#if requirement.checked}
                <Check class="check-icon" size={20} />
              {/if}
            </div>
          </button>
        </div>
      {/each}
    </div>
  </div>

  {#if allChecked}
    <div class="completion-message">
      <div class="completion-icon">
        <Check size={24} />
      </div>
      <p class="completion-text">
        すべてのハードウェア要件を確認しました。次のステップに進んでください。
      </p>
    </div>
  {/if}
</div>

<style>
  .hardware-check {
    display: flex;
    flex-direction: column;
    gap: 2rem;
    padding: 1rem;
  }

  .step-header {
    text-align: left;
  }

  .step-title {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .step-description {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  .requirements-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .section-title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--accent-color);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .requirements-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .requirement-card {
    padding: 0;
    overflow: hidden;
    transition: all 0.3s ease;
  }

  .requirement-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  }

  .requirement-button {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 1.5rem;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
  }

  .requirement-icon {
    flex-shrink: 0;
    width: 64px;
    height: 64px;
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

  .requirement-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .requirement-name {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .requirement-spec {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: var(--text-secondary);
  }

  .requirement-checkbox {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    background: rgba(0, 0, 0, 0.2);
    transition: all 0.3s ease;
  }

  .requirement-checkbox.checked {
    background: linear-gradient(
      135deg,
      var(--accent-color) 0%,
      var(--accent-color-strong) 100%
    );
    border-color: var(--accent-color);
    box-shadow: 0 0 12px var(--accent-glow);
  }

  .check-icon {
    color: white;
  }

  .diagram-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    flex-wrap: wrap;
    margin-top: 1rem;
  }

  .diagram-item {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .diagram-box {
    padding: 1rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.9375rem;
    text-align: center;
    min-width: 140px;
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
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-secondary);
  }

  .completion-message {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.25rem 1.5rem;
    background: linear-gradient(
      135deg,
      rgba(25, 211, 199, 0.15) 0%,
      rgba(25, 211, 199, 0.05) 100%
    );
    border: 1px solid rgba(25, 211, 199, 0.4);
    border-radius: 12px;
    animation: slide-in 0.3s ease-out;
  }

  @keyframes slide-in {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .completion-icon {
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--accent-color);
    color: white;
    box-shadow: 0 0 20px var(--accent-glow);
  }

  .completion-text {
    margin: 0;
    font-size: 1rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  @media (max-width: 768px) {
    .hardware-check {
      padding: 0.5rem;
      gap: 1.5rem;
    }

    .step-title {
      font-size: 1.5rem;
    }

    .section-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .requirement-button {
      flex-direction: column;
      text-align: center;
      gap: 1rem;
    }

    .requirement-content {
      align-items: center;
      text-align: center;
    }

    .diagram-content {
      flex-direction: column;
    }

    .diagram-item {
      flex-direction: column;
    }

    .diagram-arrow {
      transform: rotate(90deg);
    }
  }
</style>
