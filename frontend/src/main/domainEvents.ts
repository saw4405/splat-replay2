/**
 * ドメインイベント関連の型定義とユーティリティ
 *
 * Clean Architecture: フロントエンドがドメインイベントを直接購読し、
 * UI通知メッセージを生成する。
 */

export type DomainEventType =
  | 'domain.battle.interrupted'
  | 'domain.battle.finished'
  | 'domain.battle.started'
  | 'domain.battle.matching_started'
  | 'domain.battle.result_detected'
  | 'domain.battle.weapons_detected'
  | 'domain.battle.schedule_changed'
  | 'domain.recording.paused'
  | 'domain.recording.started'
  | 'domain.recording.resumed'
  | 'domain.recording.stopped'
  | 'domain.recording.cancelled'
  | 'domain.recording.metadata_updated'
  | 'domain.recording.audio_health_checked'
  | 'domain.asset.recorded.saved'
  | 'domain.asset.recorded.metadata_updated'
  | 'domain.asset.recorded.subtitle_updated'
  | 'domain.asset.recorded.deleted'
  | 'domain.asset.edited.saved'
  | 'domain.asset.edited.deleted'
  | 'domain.process.edit_upload_completed'
  | 'domain.process.pending'
  | 'domain.process.started'
  | 'domain.process.sleep.pending'
  | 'domain.process.sleep.started'
  | 'domain.process.sleep.cancelled'
  | 'domain.speech.listening'
  | 'domain.speech.recognized';

export interface DomainEvent {
  type: DomainEventType;
  payload: Record<string, unknown>;
}

export interface RecordingAudioHealthCheckedPayload {
  input_name?: string;
  status?: string;
  healthy?: boolean;
  short_message?: string;
  details?: string;
  peak_db?: number | null;
  event_id?: string;
  timestamp?: string;
}

export interface AutoProcessPendingPayload {
  timeout_seconds: number;
  message: string;
}

export interface AutoSleepPendingPayload {
  timeout_seconds: number;
  message: string;
  sleep_after_upload?: boolean;
}

export interface EditUploadCompletedPayload {
  success: boolean;
  message: string;
  sleep_after_upload?: boolean;
  trigger?: 'auto' | 'manual';
}

export interface SpeechRecognizedPayload {
  text?: string;
  start_seconds?: number;
  end_seconds?: number;
  event_id?: string;
  timestamp?: string;
}

/**
 * ドメインイベントのSSE購読を開始する
 *
 * @param onEvent イベントを受信したときのコールバック
 * @returns EventSourceオブジェクト（購読を停止する場合は close() を呼ぶ）
 */
export function subscribeDomainEvents(onEvent: (event: DomainEvent) => void): EventSource {
  const eventSource = new EventSource('/api/events/domain-events');

  eventSource.addEventListener('domain_event', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as DomainEvent;
      onEvent(data);
    } catch (error) {
      console.error('Failed to parse domain event:', error);
    }
  });

  eventSource.onerror = (error) => {
    console.error('Domain event SSE error:', error);
  };

  return eventSource;
}
