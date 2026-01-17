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
  | 'domain.battle.schedule_changed'
  | 'domain.recording.paused'
  | 'domain.recording.started'
  | 'domain.recording.resumed'
  | 'domain.recording.stopped'
  | 'domain.recording.cancelled'
  | 'domain.recording.metadata_updated'
  | 'domain.asset.recorded.saved'
  | 'domain.asset.recorded.metadata_updated'
  | 'domain.asset.recorded.subtitle_updated'
  | 'domain.asset.recorded.deleted'
  | 'domain.asset.edited.saved'
  | 'domain.asset.edited.deleted'
  | 'domain.speech.listening'
  | 'domain.speech.recognized';

export interface DomainEvent {
  type: DomainEventType;
  payload: Record<string, unknown>;
}

export interface BattleInterruptedPayload {
  reason?: string;
  event_id?: string;
  timestamp?: string;
}

export interface BattleFinishedPayload {
  duration_seconds?: number;
  event_id?: string;
  timestamp?: string;
}

export interface BattleStartedPayload {
  game_mode?: string;
  rate?: string | null;
  event_id?: string;
  timestamp?: string;
}

export interface RecordingPausedPayload {
  session_id?: string;
  reason?: string | null;
  event_id?: string;
  timestamp?: string;
}

export interface SpeechRecognizedPayload {
  text?: string;
  start_seconds?: number;
  end_seconds?: number;
  event_id?: string;
  timestamp?: string;
}

/**
 * ドメインイベントをUI通知メッセージに変換する
 *
 * @param event ドメインイベント
 * @returns UI通知メッセージ。通知不要な場合はnull。
 */
export function getDomainEventNotification(event: DomainEvent): string | null {
  switch (event.type) {
    case 'domain.battle.interrupted': {
      const payload = event.payload as BattleInterruptedPayload;
      if (payload.reason === 'early_abort') {
        return 'バトル中断を検出したため、録画を中止します。';
      } else if (payload.reason === 'communication_error') {
        return '通信エラーを検出したため、録画を中止します。';
      }
      return 'バトルが中断されたため、録画を中止します。';
    }

    case 'domain.battle.finished':
      return 'バトル終了を検出したため、録画を一時停止します。';

    case 'domain.battle.started':
      return 'バトル開始を検出したため、録画を開始します。';

    case 'domain.battle.matching_started':
      return 'マッチング開始を検出しました。';

    case 'domain.battle.schedule_changed':
      return 'スケジュール変更を検出しました。';

    case 'domain.recording.paused': {
      const payload = event.payload as RecordingPausedPayload;
      if (payload.reason === 'loading_detected') {
        return 'ローディング画面を検出したため、録画を一時停止します。';
      }
      return '録画を一時停止します。';
    }

    case 'domain.battle.result_detected':
      return 'バトル判定を検出しました。';

    // その他のイベントは通知不要
    case 'domain.recording.started':
    case 'domain.recording.resumed':
    case 'domain.recording.stopped':
    case 'domain.recording.cancelled':
      return null;

    default:
      return null;
  }
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
