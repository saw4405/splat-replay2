<script lang="ts">
  import { Check } from "lucide-svelte";
  import type { ProgressInfo } from "../types";

  export let progress: ProgressInfo | null = null;
</script>

{#if progress}
  <div class="progress-container">
    <span class="step-number">
      ステップ {progress.current_step_index + 1} / {progress.total_steps}
    </span>
    <div class="steps-indicator">
      {#each Array(progress.total_steps) as _, index}
        {@const isCompleted = index < progress.current_step_index}
        {@const isCurrent = index === progress.current_step_index}
        <div
          class="step-dot"
          class:completed={isCompleted}
          class:current={isCurrent}
          aria-label="ステップ {index + 1}"
        >
          {#if isCompleted}
            <Check class="check-icon" size={12} />
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .progress-container {
    width: 100%;
    padding: 1.5rem;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
  }

  .step-number {
    font-size: 0.875rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .steps-indicator {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .step-dot {
    flex: 1;
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 999px;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
  }

  .step-dot.completed {
    background: var(--accent-color);
    box-shadow: 0 0 8px var(--accent-glow);
  }

  .step-dot.current {
    background: var(--accent-color);
    box-shadow: 0 0 12px var(--accent-glow);
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }
</style>
