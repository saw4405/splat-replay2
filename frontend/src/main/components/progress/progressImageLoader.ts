export const PROGRESS_IMAGE_PRIORITY = {
  MAIN: 0,
  ACTIVE_CLIP: 1,
  ACTIVE_ITEM_REMAINDER: 2,
  NEXT_ITEM: 3,
  LATER_ITEM: 4,
} as const;

export type ProgressImagePriority =
  (typeof PROGRESS_IMAGE_PRIORITY)[keyof typeof PROGRESS_IMAGE_PRIORITY];

export interface ProgressImageReady {
  sourceUrl: string;
  objectUrl: string;
}

export interface ProgressImageRequest {
  url: string;
  ownerId: string;
  slotId: string;
  priority: ProgressImagePriority;
  sequence: number;
  onReady: (image: ProgressImageReady) => void;
  onError: (error: Error) => void;
}

export interface ProgressImageLoaderDependencies {
  fetchFn?: typeof fetch;
  decodeImage?: (objectUrl: string) => Promise<void>;
  createObjectUrl?: (blob: Blob) => string;
  revokeObjectUrl?: (objectUrl: string) => void;
  sleep?: (delayMs: number, signal: AbortSignal) => Promise<void>;
}

export interface ProgressImageLoaderContract {
  request(request: ProgressImageRequest): void;
  releaseSlot(ownerId: string, slotId: string): void;
  releaseOwner(ownerId: string): void;
  clear(): void;
  dispose(): void;
}

const RETRY_DELAYS_MS = [250, 750] as const;

async function decodeImage(objectUrl: string): Promise<void> {
  const image = new Image();
  image.src = objectUrl;
  await image.decode();
}

function sleepWithAbort(delayMs: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return Promise.reject(new DOMException('Aborted', 'AbortError'));
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, delayMs);
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

type EntryStatus = 'queued' | 'loading' | 'ready' | 'failed';

interface SlotState {
  key: string;
  request: ProgressImageRequest;
  displayedEntry: QueueEntry | null;
}

interface QueueEntry {
  sourceUrl: string;
  status: EntryStatus;
  controller: AbortController;
  objectUrl: string | null;
  error: Error | null;
  desiredSlots: Set<string>;
  displayedSlots: Set<string>;
  errorNotifiedSlots: Set<string>;
}

function slotKey(ownerId: string, slotId: string): string {
  return `${ownerId}\u0000${slotId}`;
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

export class ProgressImageLoader implements ProgressImageLoaderContract {
  private readonly slots = new Map<string, SlotState>();
  private readonly entries = new Map<string, QueueEntry>();
  private readonly fetchFn: typeof fetch;
  private readonly decodeImage: (objectUrl: string) => Promise<void>;
  private readonly createObjectUrl: (blob: Blob) => string;
  private readonly revokeObjectUrl: (objectUrl: string) => void;
  private readonly sleep: (delayMs: number, signal: AbortSignal) => Promise<void>;
  private runningEntry: QueueEntry | null = null;
  private disposed = false;

  constructor(dependencies: ProgressImageLoaderDependencies = {}) {
    this.fetchFn = dependencies.fetchFn ?? globalThis.fetch.bind(globalThis);
    this.decodeImage = dependencies.decodeImage ?? decodeImage;
    this.createObjectUrl = dependencies.createObjectUrl ?? URL.createObjectURL.bind(URL);
    this.revokeObjectUrl = dependencies.revokeObjectUrl ?? URL.revokeObjectURL.bind(URL);
    this.sleep = dependencies.sleep ?? sleepWithAbort;
  }

  request(request: ProgressImageRequest): void {
    if (this.disposed || request.url === '') return;
    const key = slotKey(request.ownerId, request.slotId);
    let slot = this.slots.get(key);
    if (slot !== undefined && slot.request.url !== request.url) {
      this.detachDesired(slot, false);
    }
    if (slot === undefined) {
      slot = { key, request, displayedEntry: null };
      this.slots.set(key, slot);
    } else {
      slot.request = request;
    }

    const entry = this.getOrCreateEntry(request.url);
    entry.desiredSlots.add(key);
    if (entry.status === 'ready' && slot.displayedEntry !== entry) {
      this.commitReadyEntry(key, entry);
    } else if (entry.status === 'failed') {
      this.notifyError(key, entry);
    } else {
      this.pump();
    }
  }

  releaseSlot(ownerId: string, slotId: string): void {
    const key = slotKey(ownerId, slotId);
    const slot = this.slots.get(key);
    if (slot === undefined) return;

    this.detachDesired(slot, true);
    if (slot.displayedEntry !== null) {
      slot.displayedEntry.displayedSlots.delete(key);
      this.cleanupEntry(slot.displayedEntry, true);
    }
    this.slots.delete(key);
  }

  releaseOwner(ownerId: string): void {
    for (const slot of [...this.slots.values()]) {
      if (slot.request.ownerId === ownerId) {
        this.releaseSlot(ownerId, slot.request.slotId);
      }
    }
  }

  clear(): void {
    for (const entry of this.entries.values()) {
      entry.controller.abort();
      if (entry.objectUrl !== null) {
        this.revokeObjectUrl(entry.objectUrl);
        entry.objectUrl = null;
      }
      entry.desiredSlots.clear();
      entry.displayedSlots.clear();
      entry.errorNotifiedSlots.clear();
    }
    this.slots.clear();
    this.entries.clear();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.clear();
  }

  private getOrCreateEntry(sourceUrl: string): QueueEntry {
    const existing = this.entries.get(sourceUrl);
    if (existing !== undefined) return existing;

    const created: QueueEntry = {
      sourceUrl,
      status: 'queued',
      controller: new AbortController(),
      objectUrl: null,
      error: null,
      desiredSlots: new Set(),
      displayedSlots: new Set(),
      errorNotifiedSlots: new Set(),
    };
    this.entries.set(sourceUrl, created);
    return created;
  }

  private detachDesired(slot: SlotState, abortIfOrphaned: boolean): void {
    const entry = this.entries.get(slot.request.url);
    if (entry === undefined) return;
    entry.desiredSlots.delete(slot.key);
    entry.errorNotifiedSlots.delete(slot.key);
    this.cleanupEntry(entry, abortIfOrphaned);
  }

  private cleanupEntry(entry: QueueEntry, abortIfOrphaned: boolean): void {
    if (entry.desiredSlots.size > 0 || entry.displayedSlots.size > 0) return;
    if (entry.status === 'loading') {
      if (abortIfOrphaned) {
        entry.controller.abort();
        this.deleteEntryIfCurrent(entry);
      }
      return;
    }
    if (entry.status === 'queued' && abortIfOrphaned) {
      entry.controller.abort();
    }
    if (entry.objectUrl !== null) {
      this.revokeObjectUrl(entry.objectUrl);
      entry.objectUrl = null;
    }
    this.deleteEntryIfCurrent(entry);
  }

  private deleteEntryIfCurrent(entry: QueueEntry): void {
    if (this.entries.get(entry.sourceUrl) === entry) {
      this.entries.delete(entry.sourceUrl);
    }
  }

  private entryRank(entry: QueueEntry): readonly [number, number] {
    let priority = Number.MAX_SAFE_INTEGER;
    let sequence = Number.MAX_SAFE_INTEGER;
    for (const key of entry.desiredSlots) {
      const request = this.slots.get(key)?.request;
      if (request === undefined) continue;
      if (
        request.priority < priority ||
        (request.priority === priority && request.sequence < sequence)
      ) {
        priority = request.priority;
        sequence = request.sequence;
      }
    }
    return [priority, sequence];
  }

  private pump(): void {
    if (this.disposed || this.runningEntry !== null) return;
    const next = [...this.entries.values()]
      .filter((entry) => entry.status === 'queued' && entry.desiredSlots.size > 0)
      .sort((left, right) => {
        const [leftPriority, leftSequence] = this.entryRank(left);
        const [rightPriority, rightSequence] = this.entryRank(right);
        return leftPriority - rightPriority || leftSequence - rightSequence;
      })[0];
    if (next === undefined) return;

    next.status = 'loading';
    this.runningEntry = next;
    void this.load(next);
  }

  private async load(entry: QueueEntry): Promise<void> {
    try {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        let candidateObjectUrl: string | null = null;
        try {
          const response = await this.fetchFn(entry.sourceUrl, {
            cache: 'no-store',
            signal: entry.controller.signal,
          });
          if (!response.ok) {
            throw new Error(`Image request failed: ${response.status}`);
          }
          const blob = await response.clone().blob();
          candidateObjectUrl = this.createObjectUrl(blob);
          await this.decodeImage(candidateObjectUrl);
          if (entry.controller.signal.aborted) {
            throw new DOMException('Aborted', 'AbortError');
          }
          entry.objectUrl = candidateObjectUrl;
          candidateObjectUrl = null;
          entry.status = 'ready';
          for (const key of [...entry.desiredSlots]) {
            this.commitReadyEntry(key, entry);
          }
          return;
        } catch (error) {
          if (candidateObjectUrl !== null) {
            this.revokeObjectUrl(candidateObjectUrl);
          }
          if (isAbortError(error) || entry.desiredSlots.size === 0) return;
          if (attempt === 2) {
            entry.status = 'failed';
            entry.error = toError(error);
            for (const key of entry.desiredSlots) {
              this.notifyError(key, entry);
            }
            return;
          }
          await this.sleep(RETRY_DELAYS_MS[attempt], entry.controller.signal);
        }
      }
    } catch (error) {
      if (!isAbortError(error) && entry.desiredSlots.size > 0) {
        entry.status = 'failed';
        entry.error = toError(error);
        for (const key of entry.desiredSlots) {
          this.notifyError(key, entry);
        }
      }
    } finally {
      if (entry.status === 'loading') entry.status = 'failed';
      if (this.runningEntry === entry) this.runningEntry = null;
      this.cleanupEntry(entry, false);
      this.pump();
    }
  }

  private commitReadyEntry(key: string, entry: QueueEntry): void {
    const slot = this.slots.get(key);
    if (slot === undefined || slot.request.url !== entry.sourceUrl || entry.objectUrl === null) {
      return;
    }

    const previous = slot.displayedEntry;
    slot.displayedEntry = entry;
    entry.displayedSlots.add(key);
    try {
      slot.request.onReady({
        sourceUrl: entry.sourceUrl,
        objectUrl: entry.objectUrl,
      });
    } catch (error) {
      void error;
    }

    if (previous !== null && previous !== entry) {
      previous.displayedSlots.delete(key);
      this.cleanupEntry(previous, true);
    }
  }

  private notifyError(key: string, entry: QueueEntry): void {
    if (entry.error === null || entry.errorNotifiedSlots.has(key)) return;
    const slot = this.slots.get(key);
    if (slot === undefined || slot.request.url !== entry.sourceUrl) return;
    entry.errorNotifiedSlots.add(key);
    try {
      slot.request.onError(entry.error);
    } catch (error) {
      void error;
    }
  }
}
