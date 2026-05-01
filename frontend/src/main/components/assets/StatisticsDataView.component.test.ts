import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { BattleHistoryEntry } from '../../api/types';
import StatisticsDataView from './StatisticsDataView.svelte';

describe('StatisticsDataView', () => {
  const battles: BattleHistoryEntry[] = [
    {
      record_id: 'record-1',
      source_video_id: 'video-1',
      game_mode: 'REGULAR_MATCH',
      started_at: '2026-04-01T10:00:00',
      match: 'REGULAR_MATCH',
      rule: 'TURF_WAR',
      stage: 'SCORCH_GORGE',
      judgement: 'WIN',
      kill: 8,
      death: 4,
      special: 3,
      assist: 1,
      gold_medals: 1,
      silver_medals: 1,
      session_rate: null,
    },
    {
      record_id: 'record-2',
      source_video_id: 'video-2',
      game_mode: 'REGULAR_MATCH',
      started_at: '2026-04-01T11:00:00',
      match: 'REGULAR_MATCH',
      rule: 'TURF_WAR',
      stage: 'SCORCH_GORGE',
      judgement: 'LOSE',
      kill: 5,
      death: 6,
      special: 2,
      assist: 0,
      gold_medals: 0,
      silver_medals: 1,
      session_rate: null,
    },
    {
      record_id: 'record-3',
      source_video_id: 'video-3',
      game_mode: 'REGULAR_MATCH',
      started_at: '2026-04-01T12:00:00',
      match: 'REGULAR_MATCH',
      rule: 'TURF_WAR',
      stage: 'SCORCH_GORGE',
      judgement: 'WIN',
      kill: 7,
      death: 3,
      special: 4,
      assist: 2,
      gold_medals: 2,
      silver_medals: 0,
      session_rate: null,
    },
  ];

  it('ルール別勝率に勝敗数を表示する', () => {
    render(StatisticsDataView, { props: { battles } });

    const turfWarRow = screen.getByRole('button', { name: /ナワバリバトル/ });

    expect(turfWarRow).toHaveTextContent('2勝1敗');
  });

  it('ステージ別勝率に勝敗数を表示する', async () => {
    render(StatisticsDataView, { props: { battles } });

    await fireEvent.click(screen.getByRole('button', { name: /ナワバリバトル/ }));

    const stageRow = screen.getByText('ユノハナ大渓谷').closest('.stage-row');

    expect(stageRow).not.toBeNull();
    expect(stageRow).toHaveTextContent('2勝1敗');
  });
});
