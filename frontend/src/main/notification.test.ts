import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { showNotificationAlways } from './notification';

describe('desktop notification client guard', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('does not call the PC notification API from LAN clients', async () => {
    vi.stubGlobal('location', { hostname: '192.168.1.20' });

    await showNotificationAlways('recording', 'started');

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('keeps calling the PC notification API from loopback clients', async () => {
    vi.stubGlobal('location', { hostname: '127.0.0.1' });

    await showNotificationAlways('recording', 'started');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/notifications/send',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });
});
