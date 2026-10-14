import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { showNotificationAlways } from './notification';

describe('desktop notification client guard', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(new Response('{"status":"success"}', { status: 200 }));
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
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => undefined);

    await showNotificationAlways('recording', 'started');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/notifications/send',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(logSpy).toHaveBeenCalledWith('[Notification] Notification sent successfully');
  });

  it.each([
    ['skipped status', new Response('{"status":"skipped"}', { status: 200 })],
    ['failure status', new Response('{"status":"failure"}', { status: 200 })],
    ['missing status', new Response('{"message":"Notification sent"}', { status: 200 })],
    ['null body', new Response('null', { status: 200 })],
    ['invalid body', new Response('not-json', { status: 200 })],
    ['HTTP failure', new Response('{"status":"success"}', { status: 500 })],
  ])('reports a %s response as failed', async (_variant, response) => {
    vi.stubGlobal('location', { hostname: '127.0.0.1' });
    fetchMock.mockResolvedValue(response);
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    await showNotificationAlways('recording', 'started');

    expect(errorSpy).toHaveBeenCalledWith('[Notification] Failed to send notification');
    expect(logSpy).not.toHaveBeenCalledWith('[Notification] Notification sent successfully');
  });
});
