import { writable } from 'svelte/store';
import type { SettingsResponse, SettingsSection } from './components/settings/types';

export type RenderMode = 'cpu' | 'gpu';

export const CPU_PREVIEW_FRAME_POLL_INTERVAL_MS = 1200;
export const GPU_PREVIEW_FRAME_POLL_INTERVAL_MS = 500;
export const CPU_DEVICE_STATUS_POLL_INTERVAL_MS = 2500;
export const GPU_DEVICE_STATUS_POLL_INTERVAL_MS = 1500;
export const CPU_PROCESS_STATUS_POLL_INTERVAL_MS = 5000;
export const GPU_PROCESS_STATUS_POLL_INTERVAL_MS = 3000;
export const UI_COUNTDOWN_TICK_INTERVAL_MS = 250;

export const renderMode = writable<RenderMode>('gpu');

export function normalizeRenderMode(value: unknown): RenderMode {
  if (typeof value === 'string' && value.toLowerCase() === 'gpu') {
    return 'gpu';
  }

  if (typeof value === 'string' && value.toLowerCase() === 'cpu') {
    return 'cpu';
  }

  return 'gpu';
}

export function resolveRenderModeFromSections(sections: SettingsSection[]): RenderMode | null {
  const webviewSection = sections.find((section) => section.id === 'webview');
  const displaySection = sections.find((section) => section.id === 'display');
  const renderModeField =
    webviewSection?.fields.find((field) => field.id === 'render_mode') ??
    displaySection?.fields.find((field) => field.id === 'render_mode') ??
    displaySection?.fields
      .find((field) => field.id === 'webview')
      ?.children?.find((field) => field.id === 'render_mode');

  if (!renderModeField) {
    return null;
  }

  return normalizeRenderMode(renderModeField.value);
}

export function resolveRenderModeFromSettingsResponse(
  response: Pick<SettingsResponse, 'sections'>
): RenderMode {
  return resolveRenderModeFromSections(response.sections) ?? 'gpu';
}

type RenderModeResponse = {
  render_mode?: unknown;
};

export function setRenderMode(mode: RenderMode, doc: Document = document): void {
  renderMode.set(mode);
  doc.documentElement.dataset.renderMode = mode;
}

export async function initializeRenderMode(doc: Document = document): Promise<RenderMode> {
  try {
    const response = await fetch('/api/settings/webview-render-mode', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`status ${response.status}`);
    }

    const data = (await response.json()) as RenderModeResponse;
    const mode = normalizeRenderMode(data.render_mode);
    setRenderMode(mode, doc);
    return mode;
  } catch {
    setRenderMode('gpu', doc);
    return 'gpu';
  }
}

export function getPreviewFramePollIntervalMs(mode: RenderMode): number {
  return mode === 'cpu' ? CPU_PREVIEW_FRAME_POLL_INTERVAL_MS : GPU_PREVIEW_FRAME_POLL_INTERVAL_MS;
}

export function getDeviceStatusPollIntervalMs(mode: RenderMode): number {
  return mode === 'cpu' ? CPU_DEVICE_STATUS_POLL_INTERVAL_MS : GPU_DEVICE_STATUS_POLL_INTERVAL_MS;
}

export function getProcessStatusPollIntervalMs(mode: RenderMode): number {
  return mode === 'cpu' ? CPU_PROCESS_STATUS_POLL_INTERVAL_MS : GPU_PROCESS_STATUS_POLL_INTERVAL_MS;
}

export function resetRenderModeForTest(doc: Document = document): void {
  renderMode.set('gpu');
  delete doc.documentElement.dataset.renderMode;
}
