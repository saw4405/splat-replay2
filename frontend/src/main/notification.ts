/**
 * Windows通知機能
 *
 * webviewが最小化されている場合に録画イベントの通知を表示する。
 * pywebview環境ではブラウザのNotification APIが使えないため、
 * バックエンドのAPI経由でWindows通知を送信する。
 */

import { shouldUseDesktopNotifications } from './clientEnvironment';

const API_BASE_URL = 'http://127.0.0.1:8000';

/**
 * バックエンド経由で通知を送信する
 *
 * @param title - 通知のタイトル
 * @param body - 通知の本文
 * @param icon - アイコンの種類
 */
async function sendNotificationViaBackend(
  title: string,
  body: string,
  icon: 'info' | 'success' | 'warning' | 'error' = 'info'
): Promise<boolean> {
  if (!shouldUseDesktopNotifications()) {
    console.log('[Notification] LAN client, skipping desktop notification');
    return false;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/notifications/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title, body, icon }),
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('[Notification] Failed to send notification:', error);
      return false;
    }

    console.log('[Notification] Notification sent successfully');
    return true;
  } catch (error) {
    console.error('[Notification] Failed to send notification:', error);
    return false;
  }
}

/**
 * ウィンドウが最小化されている（非表示の）かどうかを判定
 */
export function isWindowMinimized(): boolean {
  return document.visibilityState === 'hidden';
}

/**
 * Windows通知を表示する（最小化チェックなし）
 *
 * ウィンドウの表示状態に関係なく通知を表示します。
 *
 * @param title 通知のタイトル
 * @param body 通知の本文
 */
export async function showNotificationAlways(title: string, body: string): Promise<void> {
  console.log('[Notification] Showing notification (always):', {
    title,
    body,
  });

  try {
    const success = await sendNotificationViaBackend(title, body, 'info');

    if (success) {
      console.log('[Notification] Notification sent successfully');
    } else {
      console.error('[Notification] Failed to send notification');
    }
  } catch (error) {
    console.error('[Notification] Failed to show notification:', error);
  }
}

/**
 * Windows通知を表示する
 *
 * ウィンドウが最小化されていない場合は通知を表示しない。
 * pywebview環境ではバックエンドのAPI経由で通知を送信する。
 *
 * @param title 通知のタイトル
 * @param body 通知の本文
 */
export async function showNotification(title: string, body: string): Promise<void> {
  console.log('[Notification] Attempting to show notification:', {
    title,
    body,
    isMinimized: isWindowMinimized(),
    visibilityState: document.visibilityState,
  });

  // ウィンドウが表示されている場合は通知を表示しない
  if (!isWindowMinimized()) {
    console.log('[Notification] Window is visible, skipping notification');
    return;
  }

  try {
    console.log('[Notification] Sending notification via backend:', title);
    const success = await sendNotificationViaBackend(title, body, 'info');

    if (success) {
      console.log('[Notification] Notification sent successfully');
    } else {
      console.error('[Notification] Failed to send notification');
    }
  } catch (error) {
    console.error('[Notification] Failed to show notification:', error);
  }
}

/**
 * 録画開始時の通知を表示
 */
export async function notifyRecordingStarted(): Promise<void> {
  await showNotification('録画開始', 'バトルの録画を開始しました。');
}

/**
 * 録画一時停止時の通知を表示
 */
export async function notifyRecordingPaused(): Promise<void> {
  await showNotification('録画一時停止', 'バトルの録画を一時停止しました。');
}

/**
 * 録画再開時の通知を表示
 */
export async function notifyRecordingResumed(): Promise<void> {
  await showNotification('録画再開', 'バトルの録画を再開しました。');
}

/**
 * 録画終了時の通知を表示
 */
export async function notifyRecordingStopped(): Promise<void> {
  await showNotification('録画終了', 'バトルの録画を終了しました。');
}

/**
 * 録画キャンセル時の通知を表示
 */
export async function notifyRecordingCancelled(): Promise<void> {
  await showNotification('録画キャンセル', 'バトルの録画をキャンセルしました。');
}

/**
 * 録画準備完了時の通知を表示
 */
export async function notifyRecordingReady(): Promise<void> {
  await showNotification('自動録画の準備完了', "🎮🎮🎮 Let's play! 🎮🎮🎮");
}
