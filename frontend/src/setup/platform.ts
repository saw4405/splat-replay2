import { get } from 'svelte/store';
import { setupState } from './stores/state';
import type { SetupPlatform } from './types';

export type { SetupPlatform } from './types';

export const MACOS_APPLICATION_SUPPORT_DIR =
  '~/Library/Application Support/io.github.saw4405.splatreplay';

export function getSetupPlatform(): SetupPlatform {
  const serverPlatform = get(setupState)?.server_platform;
  return serverPlatform === 'windows' || serverPlatform === 'macos' ? serverPlatform : 'unknown';
}

export function getClientPlatform(
  platform: string = typeof navigator === 'undefined' ? '' : navigator.platform
): SetupPlatform {
  if (platform.startsWith('Win')) return 'windows';
  if (platform.startsWith('Mac')) return 'macos';
  return 'unknown';
}
