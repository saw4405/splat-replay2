import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CaptureControl from './CaptureControl.svelte';

const defaultCallbacks = {
  onStart: vi.fn(),
  onPause: vi.fn(),
  onResume: vi.fn(),
  onStop: vi.fn(),
};

describe('CaptureControl.svelte', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('バトル待受はゲームアイコンとREADYを表示し、フォーカス時だけ手動録画開始を表示する', async () => {
    render(CaptureControl, {
      props: {
        recorderState: 'STOPPED',
        switchPowerState: 'armed',
        ...defaultCallbacks,
      },
    });

    const trigger = screen.getByRole('button', {
      name: '次のバトルを自動録画する準備ができています。手動録画操作を開く',
    });
    expect(screen.getByText('READY')).toBeInTheDocument();
    expect(screen.queryByText('Stopped')).not.toBeInTheDocument();
    expect(screen.queryByRole('toolbar', { name: '手動録画操作' })).not.toBeInTheDocument();

    await fireEvent.focusIn(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('toolbar', { name: '手動録画操作' })).toBeInTheDocument();
    const startButton = screen.getByRole('button', { name: '手動録画を開始' });
    await fireEvent.click(startButton);
    expect(defaultCallbacks.onStart).toHaveBeenCalledOnce();
  });

  it('Switch電源OFFは手動操作のない状態表示にする', () => {
    render(CaptureControl, {
      props: {
        recorderState: 'STOPPED',
        switchPowerState: 'waiting_for_power_on',
        ...defaultCallbacks,
      },
    });

    expect(screen.getByRole('img', { name: 'Switchの電源が入っていません' })).toBeInTheDocument();
    expect(screen.queryByRole('toolbar', { name: '手動録画操作' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('未接続を最優先し、録画状態が残っていても手動操作を表示しない', () => {
    render(CaptureControl, {
      props: {
        recorderState: 'PAUSED',
        switchPowerState: 'capture_disconnected',
        ...defaultCallbacks,
      },
    });

    expect(screen.getByText('未接続')).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: 'キャプチャーデバイスが未接続です' })
    ).toBeInTheDocument();
    expect(screen.queryByText('PAUSE')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('録画中はRECを表示し、展開時に一時停止と停止を操作できる', async () => {
    render(CaptureControl, {
      props: {
        recorderState: 'RECORDING',
        switchPowerState: 'unknown',
        ...defaultCallbacks,
      },
    });

    const trigger = screen.getByRole('button', {
      name: '現在録画中です。手動録画操作を開く',
    });
    expect(screen.getByText('REC')).toBeInTheDocument();

    await fireEvent.focusIn(trigger);
    await fireEvent.click(screen.getByRole('button', { name: '録画を一時停止' }));
    await fireEvent.click(screen.getByRole('button', { name: '録画を停止' }));

    expect(defaultCallbacks.onPause).toHaveBeenCalledOnce();
    expect(defaultCallbacks.onStop).toHaveBeenCalledOnce();
  });

  it('一時停止は録画中より優先し、再開と停止を操作できる', async () => {
    render(CaptureControl, {
      props: {
        recorderState: 'PAUSED',
        switchPowerState: 'armed',
        ...defaultCallbacks,
      },
    });

    const trigger = screen.getByRole('button', {
      name: '録画を一時停止しています。手動録画操作を開く',
    });
    expect(screen.getByText('PAUSE')).toBeInTheDocument();

    await fireEvent.focusIn(trigger);
    await fireEvent.click(screen.getByRole('button', { name: '録画を再開' }));
    await fireEvent.click(screen.getByRole('button', { name: '録画を停止' }));

    expect(defaultCallbacks.onResume).toHaveBeenCalledOnce();
    expect(defaultCallbacks.onStop).toHaveBeenCalledOnce();
  });

  it('状態確認中は操作を表示しない', () => {
    render(CaptureControl, {
      props: {
        recorderState: 'STOPPED',
        switchPowerState: 'unknown',
        ...defaultCallbacks,
      },
    });

    expect(screen.getByRole('img', { name: '録画状態を確認しています' })).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('録画停止後はSwitch状態に応じた待受表示へ戻る', async () => {
    const { rerender } = render(CaptureControl, {
      props: {
        recorderState: 'RECORDING',
        switchPowerState: 'armed',
        ...defaultCallbacks,
      },
    });
    expect(screen.getByText('REC')).toBeInTheDocument();

    await rerender({
      recorderState: 'STOPPED',
      switchPowerState: 'armed',
      ...defaultCallbacks,
    });

    expect(screen.queryByText('REC')).not.toBeInTheDocument();
    expect(screen.getByText('READY')).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: '次のバトルを自動録画する準備ができています。手動録画操作を開く',
      })
    ).toBeInTheDocument();
  });

  it('タップで開閉でき、Escapeでは閉じて状態トリガーへ戻る', async () => {
    render(CaptureControl, {
      props: {
        recorderState: 'STOPPED',
        switchPowerState: 'armed',
        ...defaultCallbacks,
      },
    });

    const trigger = screen.getByRole('button', {
      name: '次のバトルを自動録画する準備ができています。手動録画操作を開く',
    });
    await fireEvent.pointerDown(trigger, { pointerType: 'touch' });
    await fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');

    await fireEvent.pointerDown(trigger, { pointerType: 'touch' });
    await fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await fireEvent.focusOut(trigger, { relatedTarget: null });
    await fireEvent.focusIn(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await fireEvent.keyDown(trigger, { key: 'Escape' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveFocus();
  });
});
