import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getImportedCandidateSubtitle: vi.fn(),
  listImportedVideos: vi.fn(),
  updateImportedCandidateSubtitle: vi.fn(),
}));

vi.mock('../../api/metadata', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/metadata')>()),
  getMetadataOptions: vi.fn().mockResolvedValue({
    gameModes: [],
    matches: [],
    rules: [{ key: 'turf_war', label: 'ナワバリバトル' }],
    stages: [],
    judgements: [],
  }),
}));

vi.mock('../../api/importedVideos', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/importedVideos')>();
  return { ...actual, ...api };
});

import ImportedVideoDialog from './ImportedVideoDialog.svelte';
import type { ImportedVideoJob } from '../../api/importedVideos';
import type { SubtitleData } from '../../api/types';

const readyJob: ImportedVideoJob = {
  id: 'job-1',
  source_name: 'match.mp4',
  source_suffix: '.mp4',
  state: 'ready',
  progress_percent: 100,
  duration_seconds: 30,
  has_audio: true,
  candidates: [
    {
      id: 'battle-1',
      start_seconds: 2,
      end_seconds: 21,
      segments: [[2, 21]],
      selected: true,
      metadata: { game_mode: 'battle', rule: 'turf_war' },
      title: 'バトル 1',
      description: '編集候補',
      clip_ready: true,
      duration_seconds: 19,
      has_thumbnail: true,
      has_subtitle: false,
    },
  ],
  error: null,
  title: '編集タイトル',
  description: '編集説明',
  created_at: '2026-10-23T00:00:00Z',
  has_output: true,
  has_thumbnail: true,
  has_subtitle: false,
  output_id: 'output-1',
};

describe('ImportedVideoDialog subtitle editor integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listImportedVideos.mockResolvedValue([readyJob]);
    api.getImportedCandidateSubtitle.mockResolvedValue({
      blocks: [],
      video_duration: 19,
    });
    api.updateImportedCandidateSubtitle.mockImplementation(
      async (_jobId: string, _candidateId: string, data: SubtitleData) => data
    );
  });

  afterEach(() => cleanup());

  it('字幕なし候補の編集画面を開いて空字幕を保存できる', async () => {
    const user = userEvent.setup();
    render(ImportedVideoDialog, { props: { open: true } });

    await user.click(await screen.findByRole('button', { name: /match\.mp4/ }));
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    await user.click(screen.getByText('動画・字幕を確認', { exact: true }));
    await user.click(screen.getByRole('button', { name: '字幕を編集' }));

    expect(api.getImportedCandidateSubtitle).toHaveBeenCalledWith('job-1', 'battle-1');
    expect(await screen.findByRole('heading', { name: '字幕編集' })).toBeVisible();
    expect(screen.getByText(/編集済み動画へ反映するには/)).toBeVisible();
    expect(screen.getByLabelText('字幕プレビューを再生')).toHaveAttribute(
      'src',
      '/api/imported-videos/job-1/assets/candidate/battle-1/video.mp4'
    );

    await user.click(screen.getByRole('button', { name: '保存' }));
    await waitFor(() =>
      expect(api.updateImportedCandidateSubtitle).toHaveBeenCalledWith('job-1', 'battle-1', {
        blocks: [],
        video_duration: 19,
      })
    );
  });
});
