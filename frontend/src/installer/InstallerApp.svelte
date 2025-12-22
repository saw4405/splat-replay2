<script lang="ts">
  import { installationState } from './store';
  import { InstallationStep } from './types';
  import InstallerWizard from './components/InstallerWizard.svelte';
  import {
    HardwareCheck,
    OBSSetup,
    FFMPEGSetup,
    TesseractSetup,
    FontInstallation,
    YouTubeSetup,
  } from './components/steps';

  // 各ステップのコンポーネント
  let currentStepComponent: typeof HardwareCheck | null = null;

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
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
    overflow: hidden;
    box-sizing: border-box;
  }

  @media (max-width: 768px) {
    .installer-app {
      padding: 1rem;
    }
  }
</style>
