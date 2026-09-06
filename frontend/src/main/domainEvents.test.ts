import { afterEach, describe, expect, it, vi } from 'vitest';
import { subscribeDomainEvents, type DomainEvent } from './domainEvents';

class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static readonly instances: FakeEventSource[] = [];

  readonly listeners = new Map<string, Set<EventListenerOrEventListenerObject>>();
  readyState = FakeEventSource.CONNECTING;
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  emit(type: string, event: Event): void {
    if (type === 'open') this.readyState = FakeEventSource.OPEN;
    for (const listener of this.listeners.get(type) ?? []) {
      if (typeof listener === 'function') {
        listener(event);
      } else {
        listener.handleEvent(event);
      }
    }
  }

  close(): void {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }
}

describe('subscribeDomainEvents', () => {
  afterEach(() => {
    FakeEventSource.instances.length = 0;
    vi.unstubAllGlobals();
  });

  it('複数購読を1本のEventSourceで配信し、最後の購読解除時だけ接続を閉じる', async () => {
    vi.stubGlobal('EventSource', FakeEventSource);
    const firstHandler = vi.fn<(event: DomainEvent) => void>();
    const secondHandler = vi.fn<(event: DomainEvent) => void>();
    const first = subscribeDomainEvents(firstHandler);
    const second = subscribeDomainEvents(secondHandler);

    expect(FakeEventSource.instances).toHaveLength(1);
    const source = FakeEventSource.instances[0];
    expect(source.url).toBe('/api/events/domain-events');

    source.emit('open', new Event('open'));
    const lateOpenHandler = vi.fn<(event: Event) => void>();
    const lateSubscriber = subscribeDomainEvents(vi.fn());
    lateSubscriber.onopen = lateOpenHandler;
    await Promise.resolve();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(lateOpenHandler).toHaveBeenCalledTimes(1);

    source.emit(
      'domain_event',
      new MessageEvent('domain_event', {
        data: JSON.stringify({ type: 'domain.recording.started', payload: {} }),
      })
    );
    expect(firstHandler).toHaveBeenCalledTimes(1);
    expect(secondHandler).toHaveBeenCalledTimes(1);

    first.close();
    expect(first.readyState).toBe(FakeEventSource.CLOSED);
    expect(source.closed).toBe(false);

    source.emit(
      'domain_event',
      new MessageEvent('domain_event', {
        data: JSON.stringify({ type: 'domain.recording.stopped', payload: {} }),
      })
    );
    expect(firstHandler).toHaveBeenCalledTimes(1);
    expect(secondHandler).toHaveBeenCalledTimes(2);

    second.close();
    expect(source.closed).toBe(false);
    lateSubscriber.close();
    expect(source.closed).toBe(true);
  });
});
