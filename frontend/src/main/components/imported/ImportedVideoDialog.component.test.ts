import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  cancelImportedJob: vi.fn(),
  getImportedVideo: vi.fn(),
  getImportedCandidateSubtitle: vi.fn(),
  listImportedVideos: vi.fn(),
  retryImportedScan: vi.fn(),
  startImportedEdit: vi.fn(),
  updateImportedCandidate: vi.fn(),
  updateImportedOutput: vi.fn(),
  updateImportedSourceTime: vi.fn(),
  updateImportedCandidateSubtitle: vi.fn(),
  updateImportedSelection: vi.fn(),
  updateImportedTitleDescription: vi.fn(),
  uploadImportedVideo: vi.fn(),
}));

vi.mock('../../api/metadata', () => ({
  getMetadataOptions: vi.fn().mockResolvedValue({
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

function readyJob(selected: boolean): ImportedVideoJob {
  return {
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
        selected,
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
    has_output: false,
    has_thumbnail: false,
    has_subtitle: false,
    output_id: null,
  };
}

describe('ImportedVideoDialog.svelte', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listImportedVideos.mockResolvedValue([readyJob(true)]);
    api.updateImportedCandidate.mockResolvedValue(readyJob(true));
    api.updateImportedSelection.mockImplementation(async (_id: string, ids: string[]) =>
      readyJob(ids.includes('battle-1'))
    );
  });
  afterEach(cleanup);
  async function openReady(): Promise<ReturnType<typeof userEvent.setup>> {
    const user = userEvent.setup();
    render(ImportedVideoDialog, { props: { open: true } });
    await user.click(await screen.findByRole('button', { name: /match\.mp4/ }));
    return user;
  }
  async function next(user: ReturnType<typeof userEvent.setup>, count = 1): Promise<void> {
    for (let index = 0; index < count; index += 1)
      await user.click(screen.getByRole('button', { name: '確認して次へ' }));
  }
  it('対象選択だけを表示し、解除で進めなくなる', async () => {
    const user = await openReady();
    expect(screen.queryByLabelText('キル')).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    await user.click(screen.getByRole('checkbox'));
    await waitFor(() => expect(screen.getByRole('checkbox')).not.toBeChecked());
    expect(screen.getByRole('button', { name: '内容を確認する' })).toBeDisabled();
  });
  it('選択保存失敗でサーバーの状態へ戻る', async () => {
    api.updateImportedSelection.mockRejectedValueOnce(new Error('選択保存失敗'));
    api.getImportedVideo.mockResolvedValue(readyJob(true));
    const user = await openReady();
    await user.click(screen.getByRole('checkbox'));
    await waitFor(() => expect(screen.getByRole('checkbox')).toBeChecked());
    expect(screen.getByRole('alert')).toHaveTextContent('選択保存失敗');
  });
  it('4画像を1種類ずつ確認し、修正保存後に編集結果へ進む', async () => {
    api.startImportedEdit.mockResolvedValue({
      ...readyJob(true),
      state: 'completed',
      output_id: 'output-1',
      has_output: true,
      title: '完成タイトル',
    });
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    expect(screen.getByLabelText('レート')).toBeVisible();
    expect(screen.queryByLabelText('キル')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    await next(user);
    expect(screen.getByLabelText('味方1のブキ')).toBeVisible();
    await next(user);
    await user.type(screen.getByLabelText('キル'), '0');
    await next(user);
    expect(api.updateImportedCandidate).toHaveBeenCalledWith('job-1', 'battle-1', { kill: 0 });
    expect(screen.getByLabelText('ジャッジ')).toBeVisible();
    await user.click(screen.getByRole('button', { name: '確認を終える' }));
    expect(api.startImportedEdit).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: '編集・保存する' }));
    expect(screen.getByRole('heading', { name: '編集結果を保存しました' })).toBeVisible();
    expect(screen.getByLabelText('タイトル')).toHaveValue('完成タイトル');
    expect(screen.getByLabelText('編集済み動画のプレビュー')).toHaveAttribute(
      'src',
      '/api/imported-videos/job-1/assets/output/output-1/video.mp4'
    );
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
  it('修正保存失敗で進行を止め、訂正値を保持して再試行できる', async () => {
    api.updateImportedCandidate
      .mockRejectedValueOnce(new Error('保存失敗'))
      .mockResolvedValueOnce(readyJob(true));
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    await user.type(screen.getByLabelText('レート'), '2000');
    await next(user);
    expect(screen.getByLabelText('レート')).toHaveValue('2000');
    expect(screen.getByRole('alert')).toHaveTextContent('保存失敗');
    await next(user);
    expect(screen.getByLabelText('味方1のブキ')).toBeVisible();
  });
  it('変更した数値の空欄では閉じずに修正を保持する', async () => {
    const job = readyJob(true);
    job.candidates[0].metadata.kill = 3;
    api.listImportedVideos.mockResolvedValue([job]);
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    await next(user, 2);
    await user.clear(screen.getByLabelText('キル'));
    await user.click(screen.getByRole('button', { name: '閉じる' }));
    expect(screen.getByRole('alert')).toHaveTextContent('数値を入力してください');
    expect(screen.getByLabelText('キル')).toHaveValue(null);
    expect(api.updateImportedCandidate).not.toHaveBeenCalled();
  });
  it('最後の画面から次のバトルの最初の画面へ進み、戻れる', async () => {
    const job = readyJob(true);
    job.candidates.push({ ...job.candidates[0], id: 'battle-2' });
    api.listImportedVideos.mockResolvedValue([job]);
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    await next(user, 4);
    expect(screen.getByRole('heading', { name: 'バトル 2 の確認' })).toBeVisible();
    expect(screen.getByLabelText('レート')).toBeVisible();
    await user.click(screen.getByRole('button', { name: '戻る', exact: true }));
    expect(screen.getByRole('heading', { name: 'バトル 1 の確認' })).toBeVisible();
    expect(screen.getByLabelText('ジャッジ')).toBeVisible();
  });
  it('成果物の訂正保存失敗時は切り替えず、再試行で保存する', async () => {
    const job = readyJob(true);
    job.state = 'completed';
    job.outputs = ['first', 'second'].map((id) => ({
      id,
      title: id,
      description: id,
      candidate_ids: ['battle-1'],
      has_thumbnail: false,
      has_subtitle: false,
    }));
    api.listImportedVideos.mockResolvedValue([job]);
    api.updateImportedOutput
      .mockRejectedValueOnce(new Error('成果物保存失敗'))
      .mockResolvedValueOnce(job);
    const user = await openReady();
    await user.clear(screen.getByLabelText('タイトル'));
    await user.type(screen.getByLabelText('タイトル'), '訂正タイトル');
    await user.selectOptions(screen.getByRole('combobox', { name: '編集結果' }), 'second');
    expect(screen.getByLabelText('タイトル')).toHaveValue('訂正タイトル');
    expect(screen.getByRole('combobox', { name: '編集結果' })).toHaveValue('first');
    await user.selectOptions(screen.getByRole('combobox', { name: '編集結果' }), 'second');
    expect(screen.getByLabelText('タイトル')).toHaveValue('second');
    expect(api.updateImportedOutput).toHaveBeenLastCalledWith(
      'job-1',
      'first',
      '訂正タイトル',
      'first'
    );
  });
  it('編集poll完了で最新成果物を表示する', async () => {
    api.startImportedEdit.mockResolvedValue({ ...readyJob(true), state: 'editing' });
    api.getImportedVideo.mockResolvedValue({
      ...readyJob(true),
      state: 'completed',
      output_id: 'new-output',
      title: '最新タイトル',
      has_output: true,
    });
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    await next(user, 3);
    await user.click(screen.getByRole('button', { name: '確認を終える' }));
    await user.click(screen.getByRole('button', { name: '編集・保存する' }));
    await waitFor(() => expect(screen.getByLabelText('タイトル')).toHaveValue('最新タイトル'), {
      timeout: 2000,
    });
  });
  it('ブキの未取得への訂正と表彰数を遷移時に保存する', async () => {
    const job = readyJob(true);
    job.candidates[0].metadata = {
      allies: ['旧ブキ', '', '', ''],
      gold_medals: 0,
      silver_medals: 0,
      rule: 'UNRECOGNIZED_RULE',
    };
    api.listImportedVideos.mockResolvedValue([job]);
    api.updateImportedCandidate.mockResolvedValue(job);
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    await next(user);
    await user.selectOptions(screen.getByLabelText('味方1のブキ'), '');
    await next(user);
    expect(api.updateImportedCandidate).toHaveBeenCalledWith('job-1', 'battle-1', {
      allies: ['', '', '', ''],
    });
    expect(screen.getByLabelText('ルール')).toHaveValue('UNRECOGNIZED_RULE');
    expect(screen.getByLabelText('デス')).toHaveValue(null);
    await user.clear(screen.getByLabelText('金表彰'));
    await user.type(screen.getByLabelText('金表彰'), '2');
    await user.clear(screen.getByLabelText('銀表彰'));
    await user.type(screen.getByLabelText('銀表彰'), '2');
    await next(user);
    expect(screen.getByRole('alert')).toHaveTextContent('合計は3以下');
    await user.clear(screen.getByLabelText('銀表彰'));
    await user.type(screen.getByLabelText('銀表彰'), '1');
    await next(user);
    expect(api.updateImportedCandidate).toHaveBeenLastCalledWith('job-1', 'battle-1', {
      gold_medals: 2,
      silver_medals: 1,
    });
  });
  it('開始日時の訂正は確認へ進む前に保存し、失敗時は対象選択を保つ', async () => {
    const job = readyJob(true);
    job.source_started_at = '2026-10-23T10:00:37';
    job.source_started_at_inferred = true;
    api.listImportedVideos.mockResolvedValue([job]);
    api.updateImportedSourceTime
      .mockRejectedValueOnce(new Error('日時保存失敗'))
      .mockResolvedValueOnce({ ...job, source_started_at_inferred: false });
    const user = await openReady();
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    expect(screen.getByRole('checkbox')).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('日時保存失敗');
    await user.click(screen.getByRole('button', { name: '内容を確認する' }));
    expect(screen.getByLabelText('レート')).toBeVisible();
    expect(api.updateImportedSourceTime).toHaveBeenLastCalledWith('job-1', '2026-10-23T10:00:37');
  });
  it('同名の成果物を番号で選び、それぞれの動画を確認できる', async () => {
    const job = readyJob(true);
    job.state = 'completed';
    job.output_id = 'second';
    job.outputs = ['first', 'second'].map((id) => ({
      id,
      title: '同じタイトル',
      description: id,
      candidate_ids: ['battle-1'],
      has_thumbnail: true,
      has_subtitle: false,
    }));
    api.listImportedVideos.mockResolvedValue([job]);
    const user = await openReady();
    expect(screen.getByLabelText('編集済み動画のプレビュー')).toHaveAttribute(
      'src',
      '/api/imported-videos/job-1/assets/output/second/video.mp4'
    );
    await user.selectOptions(screen.getByRole('combobox', { name: '編集結果' }), 'first');
    expect(screen.getByLabelText('編集済み動画のプレビュー')).toHaveAttribute(
      'src',
      '/api/imported-videos/job-1/assets/output/first/video.mp4'
    );
    expect(screen.getByRole('img', { name: '編集結果のサムネイル' })).toHaveAttribute(
      'src',
      '/api/imported-videos/job-1/assets/output/first/thumbnail.png'
    );
    expect(screen.getByLabelText('説明')).toHaveValue('first');
  });
  it('完了から戻る際に訂正を保存し、失敗時は完了画面に留まる', async () => {
    const job = {
      ...readyJob(true),
      state: 'completed' as const,
      output_id: 'output-1',
      has_output: true,
    };
    api.listImportedVideos.mockResolvedValue([job]);
    api.updateImportedOutput
      .mockRejectedValueOnce(new Error('保存失敗'))
      .mockResolvedValueOnce(job);
    const user = await openReady();
    await user.clear(screen.getByLabelText('タイトル'));
    await user.type(screen.getByLabelText('タイトル'), '訂正タイトル');
    await user.click(screen.getByRole('button', { name: '戻る', exact: true }));
    expect(screen.getByRole('heading', { name: '編集結果を保存しました' })).toBeVisible();
    expect(screen.getByLabelText('タイトル')).toHaveValue('訂正タイトル');
    await user.click(screen.getByRole('button', { name: '戻る', exact: true }));
    expect(screen.getByRole('button', { name: '編集・保存する' })).toBeVisible();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '戻る', exact: true }));
    expect(screen.getByRole('heading', { name: 'バトル 1 の確認' })).toBeVisible();
  });
});
