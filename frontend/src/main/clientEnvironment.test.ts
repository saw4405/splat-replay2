import { describe, expect, it } from 'vitest';
import {
  isLoopbackHost,
  shouldUseBackendPreviewFrame,
  shouldUseDesktopNotifications,
} from './clientEnvironment';

describe('client environment', () => {
  it.each(['localhost', '127.0.0.1', '127.10.20.30', '::1', '[::1]', ''])(
    'loopback host %s is treated as desktop local',
    (host) => {
      expect(isLoopbackHost(host)).toBe(true);
    }
  );

  it.each(['192.168.1.20', '10.0.0.5', 'splat-replay.local'])(
    'LAN host %s is not treated as desktop local',
    (host) => {
      expect(isLoopbackHost(host)).toBe(false);
    }
  );

  it('uses backend preview frames for video files and LAN live capture', () => {
    expect(shouldUseBackendPreviewFrame('video_file', '127.0.0.1')).toBe(true);
    expect(shouldUseBackendPreviewFrame('live_capture', '192.168.1.20')).toBe(true);
    expect(shouldUseBackendPreviewFrame('live_capture', '127.0.0.1')).toBe(false);
  });

  it('limits desktop notification calls to loopback clients', () => {
    expect(shouldUseDesktopNotifications('127.0.0.1')).toBe(true);
    expect(shouldUseDesktopNotifications('localhost')).toBe(true);
    expect(shouldUseDesktopNotifications('192.168.1.20')).toBe(false);
  });
});
