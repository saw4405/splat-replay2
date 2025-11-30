<script lang="ts">
  export let message: string;
</script>

<div class="video-preview glass-panel">
  <div class="message-panel glass-panel">
    <p>{message}</p>
  </div>
</div>

<style>
  .video-preview {
    position: relative;
    width: 100%;
    height: 100%;
    background: var(--glass-bg-strong);
    border-radius: calc(var(--glass-radius) + 4px);
    overflow: hidden;
    display: block;
    padding: 0;
    box-sizing: border-box;
    box-shadow:
      var(--glass-shadow),
      inset 0 0 60px rgba(25, 211, 199, 0.06);
  }

  .message-panel {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    max-height: 100%;
    padding: 2rem;
    text-align: center;
    color: var(--text-primary);
    box-sizing: border-box;
    overflow: auto;
    gap: 1rem;
  }

  .message-panel p {
    font-size: clamp(1rem, 2.4vw, 1.25rem);
    font-weight: 500;
    margin: 0;
    line-height: 1.6;
    word-break: break-word;
    white-space: pre-wrap;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  }
</style>
