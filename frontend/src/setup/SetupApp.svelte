<script lang="ts">
  import { setupState } from './stores/state';
  import { SetupStep } from './types';
  import SetupWizard from './components/SetupWizard.svelte';
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

  $: if ($setupState) {
    // 現在のステップに応じてコンポーネントを切り替え
    switch ($setupState.current_step) {
      case SetupStep.HARDWARE_CHECK:
        currentStepComponent = HardwareCheck;
        break;
      case SetupStep.OBS_SETUP:
        currentStepComponent = OBSSetup;
        break;
      case SetupStep.FFMPEG_SETUP:
        currentStepComponent = FFMPEGSetup;
        break;
      case SetupStep.TESSERACT_SETUP:
        currentStepComponent = TesseractSetup;
        break;
      case SetupStep.FONT_INSTALLATION:
        currentStepComponent = FontInstallation;
        break;
      case SetupStep.YOUTUBE_SETUP:
        currentStepComponent = YouTubeSetup;
        break;
      default:
        currentStepComponent = null;
    }
  }
</script>

<main class="setup-app">
  <SetupWizard {currentStepComponent}></SetupWizard>
</main>

<style>
  .setup-app {
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
    .setup-app {
      padding: 1rem;
    }
  }
</style>
