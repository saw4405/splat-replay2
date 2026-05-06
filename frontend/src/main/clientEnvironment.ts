import type { RecorderPreviewMode } from './api/types';

export function normalizeHostname(hostname: string = globalThis.location?.hostname ?? ''): string {
  return hostname.trim().toLowerCase().replace(/^\[/, '').replace(/\]$/, '');
}

export function isLoopbackHost(hostname: string = globalThis.location?.hostname ?? ''): boolean {
  const normalized = normalizeHostname(hostname);
  return (
    normalized === '' ||
    normalized === 'localhost' ||
    normalized === '::1' ||
    normalized === '0:0:0:0:0:0:0:1' ||
    normalized.startsWith('127.')
  );
}

export function shouldUseBackendPreviewFrame(
  mode: RecorderPreviewMode,
  hostname: string = globalThis.location?.hostname ?? ''
): boolean {
  return mode === 'video_file' || !isLoopbackHost(hostname);
}

export function shouldUseDesktopNotifications(
  hostname: string = globalThis.location?.hostname ?? ''
): boolean {
  return isLoopbackHost(hostname);
}
