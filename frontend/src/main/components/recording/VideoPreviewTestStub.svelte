<script lang="ts">
  import type { SwitchPowerState } from '../../api/types';

  let { switchPowerState = 'unknown' }: { switchPowerState?: SwitchPowerState } = $props();
</script>

<div data-testid="video-preview-stub" data-switch-power-state={switchPowerState}></div>
