/**
 * セットアップ状態管理 - 設定管理
 *
 * 責務：
 * - OBS設定の取得・保存
 * - ビデオデバイスの取得・保存
 * - YouTube設定の保存
 */

import { API_BASE_URL, isLoading, error, handleApiError, safeParseJson } from './state';
import type { MessageResponse } from '../types';

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
