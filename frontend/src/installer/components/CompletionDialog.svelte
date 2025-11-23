<script lang="ts">
  import { CheckCircle2, ArrowRight } from "lucide-svelte";

  export let open = false;
  export let onContinue: (() => void) | undefined = undefined;

  function handleContinue(): void {
    open = false;
    if (onContinue) {
      onContinue();
    }
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      handleContinue();
    }
  }
</script>

{#if open}
  <div
    class="dialog-backdrop"
    on:click={handleBackdropClick}
    on:keydown={(e) => e.key === "Escape" && handleContinue()}
    role="button"
    tabindex="0"
  >
    <div class="dialog-container glass-surface" role="dialog" aria-modal="true">
      <div class="dialog-icon">
        <CheckCircle2 size={64} />
      </div>

      <div class="dialog-content">
        <h2 class="dialog-title">セットアップ完了！</h2>
        <p class="dialog-message">
          Splat Replay のセットアップが完了しました。<br />
          これでアプリケーションを使用する準備が整いました。
        </p>
        <p class="dialog-submessage">
          メインアプリケーション画面に移動します。
        </p>
      </div>

      <div class="dialog-actions">
        <button
          class="button button-primary"
          type="button"
          on:click={handleContinue}
        >
          アプリケーションを開始
          <ArrowRight class="button-icon" size={20} />
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
    animation: fade-in 0.2s ease-out;
  }

  @keyframes fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .dialog-container {
    width: 100%;
    max-width: 500px;
    padding: 2.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2rem;
    animation: slide-up 0.3s ease-out;
  }

  @keyframes slide-up {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .dialog-icon {
    width: 96px;
    height: 96px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(
      135deg,
      rgba(25, 211, 199, 0.2) 0%,
      rgba(25, 211, 199, 0.05) 100%
    );
    border: 3px solid var(--accent-color);
    color: var(--accent-color);
    box-shadow: 0 0 40px var(--accent-glow);
    animation: pulse-glow 2s ease-in-out infinite;
  }

  @keyframes pulse-glow {
    0%,
    100% {
      box-shadow: 0 0 40px var(--accent-glow);
    }
    50% {
      box-shadow: 0 0 60px var(--accent-glow);
    }
  }

  .dialog-content {
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .dialog-title {
    margin: 0;
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent-color);
    text-shadow: 0 0 20px var(--accent-glow);
  }

  .dialog-message {
    margin: 0;
    font-size: 1.125rem;
    line-height: 1.6;
    color: var(--text-primary);
  }

  .dialog-submessage {
    margin: 0;
    font-size: 1rem;
    color: var(--text-secondary);
  }

  .dialog-actions {
    display: flex;
    gap: 1rem;
    width: 100%;
  }

  .button {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1rem 2rem;
    font-size: 1.125rem;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    white-space: nowrap;
  }

  .button-primary {
    background: linear-gradient(
      135deg,
      var(--accent-color) 0%,
      var(--accent-color-strong) 100%
    );
    color: white;
    border-color: var(--accent-color);
  }

  .button-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px var(--accent-glow);
  }

  .button-icon {
    display: block;
    flex-shrink: 0;
  }

  @media (max-width: 768px) {
    .dialog-container {
      padding: 2rem;
    }

    .dialog-title {
      font-size: 1.75rem;
    }

    .dialog-message {
      font-size: 1rem;
    }

    .button {
      padding: 0.875rem 1.5rem;
      font-size: 1rem;
    }
  }
</style>
