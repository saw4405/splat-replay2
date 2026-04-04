import { get } from 'svelte/store';
import { afterEach, describe, expect, it } from 'vitest';
import { SetupStep, type SetupState } from '../types';
import { progressInfo, setupState } from './state';

describe('setup progressInfo', () => {
  afterEach(() => {
    setupState.set(null);
  });

  it('FFmpeg を OBS より先のステップとして扱う', () => {
    const state: SetupState = {
      is_completed: false,
      current_step: SetupStep.FFMPEG_SETUP,
      completed_steps: [SetupStep.HARDWARE_CHECK],
      skipped_steps: [],
      step_details: {
        [SetupStep.HARDWARE_CHECK]: {
          device_detected: true,
        },
        [SetupStep.FFMPEG_SETUP]: {},
      },
      installation_date: null,
    };

    setupState.set(state);

    expect(get(progressInfo)).toMatchObject({
      current_step_index: 1,
      total_steps: 7,
      current_step_name: SetupStep.FFMPEG_SETUP,
    });
  });
});
