import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { subscribeDomainEventsMock, eventSourceCloseMock } = vi.hoisted(() => ({
  subscribeDomainEventsMock: vi.fn(),
  eventSourceCloseMock: vi.fn(),
}));

vi.mock('../../domainEvents', () => ({
  subscribeDomainEvents: subscribeDomainEventsMock,
}));

import MetadataOverlay from './MetadataOverlay.svelte';

type LiveMetadataResponse = {
  game_mode: string;
  started_at: string;
  match: string;
  rule: string;
  rate: string;
  judgement: string;
  stage: string;
  kill: number;
  death: number;
  special: number;
  gold_medals: number;
  silver_medals: number;
  allies: string[];
  enemies: string[];
};

describe('MetadataOverlay.svelte', () => {
  const metadataOptionsResponse = {
    game_modes: [{ key: 'BATTLE', label: 'バトル' }],
    matches: [{ key: 'REGULAR', label: 'レギュラーマッチ' }],
    rules: [
      { key: 'NAWABARI', label: 'ナワバリバトル' },
      { key: 'AREA', label: 'ガチエリア' },
    ],
    stages: [{ key: 'YAGARA_MARKET', label: 'ヤガラ市場' }],
    judgements: [{ key: 'WIN', label: '勝ち' }],
  };

  let fetchMock: ReturnType<typeof vi.fn>;

  function createLiveMetadata(overrides: Partial<LiveMetadataResponse> = {}): LiveMetadataResponse {
    return {
      game_mode: 'BATTLE',
      started_at: '2026-03-14 10:00:00',
      match: 'REGULAR',
      rule: 'NAWABARI',
      rate: '2500',
      judgement: 'WIN',
      stage: 'YAGARA_MARKET',
      kill: 8,
      death: 4,
      special: 2,
      gold_medals: 2,
      silver_medals: 1,
      allies: ['A', 'B', 'C', 'D'],
      enemies: ['E', 'F', 'G', 'H'],
      ...overrides,
    };
  }

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
    eventSourceCloseMock.mockReset();
    subscribeDomainEventsMock.mockReset();
    subscribeDomainEventsMock.mockReturnValue({
      close: eventSourceCloseMock,
      readyState: 1,
      onerror: null,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('Now ボタンで開始時間を現在時刻形式へ更新できる', async () => {
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/metadata/options')) {
        return new Response(JSON.stringify(metadataOptionsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/recorder/metadata')) {
        return new Response(JSON.stringify(createLiveMetadata()), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(MetadataOverlay, {
      props: { visible: true },
    });

    const startedAtInput = (await screen.findByLabelText('開始時間')) as HTMLInputElement;
    await waitFor(() => {
      expect(startedAtInput.value).toBe('2026-03-14 10:00:00');
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Now' }));

    expect(startedAtInput.value).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(startedAtInput.value).not.toBe('2026-03-14 10:00:00');
  });

  it('リセットで最新メタデータを再取得して未保存変更を捨てる', async () => {
    let metadataFetchCount = 0;
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/metadata/options')) {
        return new Response(JSON.stringify(metadataOptionsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/recorder/metadata')) {
        metadataFetchCount += 1;
        const body =
          metadataFetchCount === 1
            ? createLiveMetadata({ kill: 8 })
            : createLiveMetadata({ kill: 3 });
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(MetadataOverlay, {
      props: { visible: true },
    });

    const killInput = (await screen.findByLabelText('キル数')) as HTMLInputElement;
    await waitFor(() => {
      expect(killInput.value).toBe('8');
    });

    await fireEvent.input(killInput, { target: { value: '20' } });
    expect(killInput.value).toBe('20');

    await fireEvent.click(screen.getByRole('button', { name: 'リセット' }));

    await waitFor(() => {
      expect(killInput.value).toBe('3');
    });
    expect(metadataFetchCount).toBeGreaterThanOrEqual(2);
  });

  it('再マウント時は未保存変更を持ち越さず現在値を再取得する', async () => {
    let metadataFetchCount = 0;
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.includes('/api/metadata/options')) {
        return new Response(JSON.stringify(metadataOptionsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/recorder/metadata')) {
        metadataFetchCount += 1;
        const body =
          metadataFetchCount === 1
            ? createLiveMetadata({ kill: 8 })
            : createLiveMetadata({ kill: 5 });
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    const firstRender = render(MetadataOverlay, {
      props: { visible: true },
    });

    const firstKillInput = (await screen.findByLabelText('キル数')) as HTMLInputElement;
    await waitFor(() => {
      expect(firstKillInput.value).toBe('8');
    });

    await fireEvent.input(firstKillInput, { target: { value: '30' } });
    expect(firstKillInput.value).toBe('30');

    firstRender.unmount();

    render(MetadataOverlay, {
      props: { visible: true },
    });

    const secondKillInput = (await screen.findByLabelText('キル数')) as HTMLInputElement;
    await waitFor(() => {
      expect(secondKillInput.value).toBe('5');
    });
    expect(metadataFetchCount).toBe(2);
  });
});
