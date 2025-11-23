<script lang="ts">
  import { installationState } from "./store";
  import { InstallationStep } from "./types";
  import InstallerWizard from "./components/InstallerWizard.svelte";
  import {
    HardwareCheck,
    OBSSetup,
    FFMPEGSetup,
    TesseractSetup,
    FontInstallation,
    YouTubeSetup,
  } from "./components/steps";

  // 各ステップのコンポーネント
  let currentStepComponent: any = null;

  $: if ($installationState) {
    // 現在のステップに応じてコンポーネントを切り替え
    switch ($installationState.current_step) {
      case InstallationStep.HARDWARE_CHECK:
        currentStepComponent = HardwareCheck;
        break;
      case InstallationStep.OBS_SETUP:
        currentStepComponent = OBSSetup;
        break;
      case InstallationStep.FFMPEG_SETUP:
        currentStepComponent = FFMPEGSetup;
        break;
      case InstallationStep.TESSERACT_SETUP:
        currentStepComponent = TesseractSetup;
        break;
      case InstallationStep.FONT_INSTALLATION:
        currentStepComponent = FontInstallation;
        break;
      case InstallationStep.YOUTUBE_SETUP:
        currentStepComponent = YouTubeSetup;
        break;
      default:
        currentStepComponent = null;
    }
  }
</script>

<main class="installer-app">
  <InstallerWizard {currentStepComponent}></InstallerWizard>
</main>

<style>
  .installer-app {
    width: 100%;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .step-placeholder {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .placeholder-card {
    width: 100%;
    text-align: center;
  }

  .placeholder-title {
    margin: 0 0 1rem 0;
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--accent-color);
  }

  .placeholder-description {
    margin: 0 0 2rem 0;
    font-size: 1rem;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .placeholder-info {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.5rem;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    text-align: left;
  }

  .placeholder-info p {
    margin: 0;
    font-size: 0.9375rem;
    color: var(--text-primary);
  }

  .placeholder-info code {
    padding: 0.25rem 0.5rem;
    background: rgba(25, 211, 199, 0.1);
    border: 1px solid rgba(25, 211, 199, 0.3);
    border-radius: 4px;
    font-family: monospace;
    color: var(--accent-color);
  }

  @media (max-width: 768px) {
    .installer-app {
      padding: 1rem;
    }

    .step-placeholder {
      padding: 1rem;
    }

    .placeholder-title {
      font-size: 1.5rem;
    }
  }
</style>
