import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AutoProcessNotification from './AutoProcessNotification.svelte';

describe('AutoProcessNotification.svelte', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('キャンセル操作を一度だけバックエンドへ委譲して閉じる', async () => {
    const onCancel = vi.fn().mockResolvedValue(undefined);
    const onDismiss = vi.fn();
    render(AutoProcessNotification, {
      props: {
        payload: { timeout_seconds: 15, message: '15秒後に開始します' },
        onCancel,
        onDismiss,
      },
    });

    const cancelButton = screen.getByRole('button', { name: 'キャンセル' });
    await fireEvent.click(cancelButton);
    await fireEvent.click(cancelButton);

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('猶予満了時は表示だけを閉じ、ブラウザから開始要求を送らない', async () => {
    vi.useFakeTimers();
    const onCancel = vi.fn();
    const onDismiss = vi.fn();
    render(AutoProcessNotification, {
      props: {
        payload: { timeout_seconds: 1, message: '1秒後に開始します' },
        onCancel,
        onDismiss,
      },
    });

    await vi.advanceTimersByTimeAsync(1100);

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });
});
