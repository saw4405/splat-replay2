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
  cancelled?: boolean;
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

type DomainEventHandler = (event: DomainEvent) => void;
type ConnectionEventHandler = (event: Event) => void;

export interface DomainEventSubscription {
  onopen: ConnectionEventHandler | null;
  onerror: ConnectionEventHandler | null;
  readonly readyState: number;
  close(): void;
}

interface Subscriber extends DomainEventSubscription {
  onEvent: DomainEventHandler;
  openNotified: boolean;
  closed: boolean;
}

const subscribers = new Set<Subscriber>();
let sharedEventSource: EventSource | null = null;

function notifyConnectionEvent(kind: 'onopen' | 'onerror', event: Event): void {
  for (const subscriber of [...subscribers]) {
    if (subscriber.closed) continue;
    const handler = subscriber[kind];
    if (!handler) continue;
    if (kind === 'onopen') {
      subscriber.openNotified = true;
    }
    try {
      handler(event);
    } catch (error) {
      console.error(`Domain event subscriber ${kind} failed:`, error);
    }
  }
}

function openSharedEventSource(): EventSource {
  const source = new EventSource('/api/events/domain-events');

  source.addEventListener('domain_event', (event: MessageEvent) => {
    let data: DomainEvent;
    try {
      data = JSON.parse(event.data) as DomainEvent;
    } catch (error) {
      console.error('Failed to parse domain event:', error);
      return;
    }

    for (const subscriber of [...subscribers]) {
      if (subscriber.closed) continue;
      try {
        subscriber.onEvent(data);
      } catch (error) {
        console.error('Domain event subscriber failed:', error);
      }
    }
  });
  source.addEventListener('open', (event: Event) => {
    notifyConnectionEvent('onopen', event);
  });
  source.addEventListener('error', (event: Event) => {
    console.error('Domain event SSE error:', event);
    notifyConnectionEvent('onerror', event);
  });

  sharedEventSource = source;
  return source;
}

/**
 * ドメインイベントのSSE購読を開始する
 *
 * @param onEvent イベントを受信したときのコールバック
 * @returns 共有SSEの購読（購読を停止する場合は close() を呼ぶ）
 */
export function subscribeDomainEvents(onEvent: DomainEventHandler): DomainEventSubscription {
  const subscriber: Subscriber = {
    onEvent,
    onopen: null,
    onerror: null,
    openNotified: false,
    closed: false,
    get readyState() {
      return subscriber.closed ? EventSource.CLOSED : source.readyState;
    },
    close() {
      if (subscriber.closed) return;
      subscriber.closed = true;
      subscribers.delete(subscriber);
      if (subscribers.size === 0) {
        sharedEventSource?.close();
        sharedEventSource = null;
      }
    },
  };
  subscribers.add(subscriber);
  const source = sharedEventSource ?? openSharedEventSource();

  queueMicrotask(() => {
    const handler = subscriber.onopen;
    if (
      !subscriber.closed &&
      !subscriber.openNotified &&
      source.readyState === EventSource.OPEN &&
      handler
    ) {
      subscriber.openNotified = true;
      try {
        handler(new Event('open'));
      } catch (error) {
        console.error('Domain event subscriber onopen failed:', error);
      }
    }
  });

  return subscriber;
}
