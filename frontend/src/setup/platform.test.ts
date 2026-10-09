import { afterEach, describe, expect, it } from 'vitest';
import { getClientPlatform, getSetupPlatform } from './platform';
import { setupState } from './stores/state';
import { SetupStep, type SetupPlatform } from './types';

afterEach(() => {
  setupState.set(null);
});

describe('getSetupPlatform', () => {
  it('setup status の server_platform を返す', () => {
    setupState.set({
      is_completed: false,
      current_step: SetupStep.HARDWARE_CHECK,
      completed_steps: [],
      skipped_steps: [],
      step_details: {},
      installation_date: null,
      server_platform: 'macos',
    });

    expect(getSetupPlatform()).toBe('macos');
  });

  it('status 未取得または server_platform 欠落時は unknown を返す', () => {
    expect(getSetupPlatform()).toBe('unknown');

    setupState.set({
      is_completed: false,
      current_step: SetupStep.HARDWARE_CHECK,
      completed_steps: [],
      skipped_steps: [],
      step_details: {},
      installation_date: null,
    });

    expect(getSetupPlatform()).toBe('unknown');
  });

  it('未知の server_platform を unknown に正規化する', () => {
    setupState.set({
      is_completed: false,
      current_step: SetupStep.HARDWARE_CHECK,
      completed_steps: [],
      skipped_steps: [],
      step_details: {},
      installation_date: null,
      server_platform: 'freebsd' as unknown as SetupPlatform,
    });

    expect(getSetupPlatform()).toBe('unknown');
  });
});

describe('getClientPlatform', () => {
  it('navigator platform から video client のOSを判別する', () => {
    expect(getClientPlatform('Win32')).toBe('windows');
    expect(getClientPlatform('MacIntel')).toBe('macos');
    expect(getClientPlatform('Linux x86_64')).toBe('unknown');
    expect(getClientPlatform('iPhone')).toBe('unknown');
    expect(getClientPlatform('')).toBe('unknown');
  });
});
