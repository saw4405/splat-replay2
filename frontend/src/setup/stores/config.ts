/**
 * セットアップ状態管理 - 設定管理
 *
 * 責務：
 * - OBS設定の取得・保存
 * - ビデオデバイスの取得・保存
 * - YouTube設定の保存
 * - 文字起こし設定の取得・保存
 * - マイクデバイスの取得
 */

import { API_BASE_URL, isLoading, error, handleApiError, safeParseJson } from './state';
import type { SettingsResponse } from '../../main/components/settings/types';
import type { MessageResponse } from '../types';

export type TranscriptionConfig = {
  enabled: boolean;
  micDeviceName: string;
  groqApiKey: string;
  language: string;
  customDictionary: string[];
};

function getSectionFieldValue(
  response: SettingsResponse,
  sectionId: string,
  fieldId: string
): unknown {
  const section = response.sections.find((item) => item.id === sectionId);
  const field = section?.fields.find((item) => item.id === fieldId);
  return field?.value;
}

function asString(value: unknown, fallback: string = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

/**
 * OBS設定を取得
 */
export async function getOBSConfig(): Promise<{
  websocket_password: string;
  capture_device_name: string;
}> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/config/obs`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<{
      websocket_password: string;
      capture_device_name: string;
    }>(response);
    return result;
  } catch (err) {
    console.error('Failed to get OBS config:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * OBS WebSocketパスワードを保存
 */
export async function saveOBSWebSocketPassword(password: string): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/config/obs/websocket-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<MessageResponse>(response);
    console.log('OBS WebSocket password saved:', result.message);
  } catch (err) {
    console.error('Failed to save OBS WebSocket password:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * ビデオキャプチャデバイス一覧を取得
 */
export async function listVideoDevices(): Promise<string[]> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/devices/video`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<{ devices: string[] }>(response);
    return result.devices;
  } catch (err) {
    console.error('Failed to list video devices:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * マイクデバイス一覧を取得
 */
export async function listMicrophones(): Promise<string[]> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/devices/audio`);
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<{ devices: string[] }>(response);
    return result.devices;
  } catch (err) {
    console.error('Failed to list microphones:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * キャプチャデバイス名を保存
 */
export async function saveCaptureDevice(deviceName: string): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/config/capture-device`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ device_name: deviceName }),
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<MessageResponse>(response);
    console.log('Capture device saved:', result.message);
  } catch (err) {
    console.error('Failed to save capture device:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * YouTube公開範囲を保存
 */
export async function saveYouTubePrivacyStatus(
  privacyStatus: 'public' | 'unlisted' | 'private'
): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/setup/config/youtube/privacy-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ privacy_status: privacyStatus }),
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<MessageResponse>(response);
    console.log('YouTube privacy status saved:', result.message);
  } catch (err) {
    console.error('Failed to save YouTube privacy status:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * 文字起こし設定を取得
 */
export async function getTranscriptionConfig(): Promise<TranscriptionConfig> {
  isLoading.set(true);
  error.set(null);

  try {
    const response = await fetch(`${API_BASE_URL}/api/settings`, { cache: 'no-store' });
    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await safeParseJson<SettingsResponse>(response);
    const enabledValue = getSectionFieldValue(data, 'speech_transcriber', 'enabled');
    return {
      enabled: typeof enabledValue === 'boolean' ? enabledValue : true,
      micDeviceName: asString(getSectionFieldValue(data, 'speech_transcriber', 'mic_device_name')),
      groqApiKey: asString(getSectionFieldValue(data, 'speech_transcriber', 'groq_api_key')),
      language: asString(getSectionFieldValue(data, 'speech_transcriber', 'language'), 'ja-JP'),
      customDictionary: asStringList(
        getSectionFieldValue(data, 'speech_transcriber', 'custom_dictionary')
      ),
    };
  } catch (err) {
    console.error('Failed to get transcription config:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}

/**
 * 文字起こし設定を保存
 */
export async function saveTranscriptionConfig(config: TranscriptionConfig): Promise<void> {
  isLoading.set(true);
  error.set(null);

  try {
    const payload = {
      sections: [
        {
          id: 'speech_transcriber',
          values: {
            enabled: config.enabled,
            mic_device_name: config.micDeviceName,
            groq_api_key: config.groqApiKey,
            language: config.language,
            custom_dictionary: config.customDictionary,
          },
        },
      ],
    };
    const response = await fetch(`${API_BASE_URL}/api/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      await handleApiError(response);
    }

    const result = await safeParseJson<{ status: string }>(response);
    console.log('Transcription config saved:', result.status);
  } catch (err) {
    console.error('Failed to save transcription config:', err);
    if (err instanceof Error) {
      error.set({ error: err.message });
    }
    throw err;
  } finally {
    isLoading.set(false);
  }
}
