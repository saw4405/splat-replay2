import { expect, test } from '@playwright/test';

import { environment, gotoMain, resetReplayTestState } from './support/appHelpers';
import type { ImportedVideoJob } from '../../src/main/api/importedVideos';

const e2eEnvironment = environment();

function importedJob(overrides: Partial<ImportedVideoJob> = {}): ImportedVideoJob {
  return {
    id: 'job-import-1',
    source_name: '持込試合.mkv',
    source_suffix: '.mkv',
    state: 'ready',
    progress_percent: 100,
    duration_seconds: 150,
    has_audio: true,
    candidates: [
      {
        id: 'battle-1',
        start_seconds: 8,
        end_seconds: 124,
        segments: [[8, 124]],
        selected: true,
        metadata: { rule: 'turf_war', stage: 'mincemeat_metalworks' },
        title: '対戦 1: WIN / ゴンズイ地区',
        description: 'ナワバリバトル・ゴンズイ地区。',
        clip_ready: true,
        duration_seconds: 116,
        has_thumbnail: true,
        has_subtitle: false,
      },
    ],
    error: null,
    title: null,
    description: null,
    created_at: '2026-10-23T00:00:00+09:00',
    has_output: false,
    has_thumbnail: false,
    has_subtitle: false,
    output_id: null,
    ...overrides,
  };
}

test('プレビューへの動画ドロップで開き、投稿せず編集済み動画を保存できる', async ({ page }) => {
  resetReplayTestState(e2eEnvironment);
  await gotoMain(page);

  let job: ImportedVideoJob | null = null;
  let uploadFilename = '';
  let candidateSubtitleSaved = false;
  let candidateMetadataSaved = false;
  await page.route('**/api/imported-videos**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/assets/source') || path.includes('/assets/')) {
      await route.fulfill({ status: 200, contentType: 'video/mp4', body: '' });
      return;
    }
    if (path === '/api/imported-videos/job-import-1/candidates/battle-1/subtitle') {
      if (request.method() === 'GET') {
        await route.fulfill({ status: 200, json: { blocks: [], video_duration: 116 } });
        return;
      }
      if (request.method() === 'PUT') {
        candidateSubtitleSaved = true;
        await route.fulfill({ status: 200, json: request.postDataJSON() });
        return;
      }
    }
    if (request.method() === 'POST' && path === '/api/imported-videos') {
      uploadFilename = request.headers()['x-file-name'] ?? '';
      job = importedJob();
      await route.fulfill({ status: 200, json: job });
      return;
    }
    if (request.method() === 'GET' && path === '/api/imported-videos') {
      await route.fulfill({ status: 200, json: job ? [job] : [] });
      return;
    }
    if (request.method() === 'PUT' && path.endsWith('/selection')) {
      const body = request.postDataJSON() as { candidate_ids: string[] };
      job = importedJob({
        candidates: importedJob().candidates.map((candidate) => ({
          ...candidate,
          selected: body.candidate_ids.includes(candidate.id),
        })),
      });
      await route.fulfill({ status: 200, json: job });
      return;
    }
    if (request.method() === 'PATCH' && path === '/api/imported-videos/job-import-1') {
      const body = request.postDataJSON() as { title: string; description: string };
      job = importedJob({ title: body.title, description: body.description });
      await route.fulfill({ status: 200, json: job });
      return;
    }
    if (
      request.method() === 'PATCH' &&
      path === '/api/imported-videos/job-import-1/candidates/battle-1'
    ) {
      const patch = request.postDataJSON() as { metadata: Record<string, string | number | null> };
      job = importedJob({
        candidates: importedJob().candidates.map((candidate) => ({
          ...candidate,
          metadata: { ...candidate.metadata, ...patch.metadata },
        })),
      });
      candidateMetadataSaved = job.candidates[0].metadata.kill === 3;
      await route.fulfill({ status: 200, json: job });
      return;
    }
    if (request.method() === 'POST' && path.endsWith('/edit')) {
      expect(candidateMetadataSaved).toBe(true);
      job = importedJob({
        state: 'completed',
        title: 'つなげた試合',
        description: '選んだバトル',
        has_output: true,
        has_thumbnail: true,
        output_id: 'output-1',
      });
      await route.fulfill({ status: 200, json: job });
      return;
    }
    if (request.method() === 'GET' && path === '/api/imported-videos/job-import-1') {
      await route.fulfill({ status: 200, json: job ?? importedJob() });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: 'unexpected imported video request' } });
  });

  await expect(page.getByRole('button', { name: '動画を取り込んで編集' })).toHaveCount(0);
  await page.getByTestId('preview-container').evaluate((preview) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['local video'], '持込試合.mkv', { type: 'video/x-matroska' }));
    preview.dispatchEvent(
      new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer })
    );
  });

  await expect(page.getByRole('dialog', { name: '動画を取り込んで編集' })).toBeVisible();
  await expect(page.getByRole('checkbox', { name: '1番目のバトルを編集に含める' })).toBeChecked();
  await page.getByRole('button', { name: '内容を確認する' }).click();
  await expect(page.getByLabel('レート', { exact: true })).toBeVisible();
  await expect(page.getByLabel('キル', { exact: true })).toHaveCount(0);
  expect(uploadFilename).toBe(encodeURIComponent('持込試合.mkv'));

  await page.getByText('動画・字幕を確認', { exact: true }).click();
  await page.getByRole('button', { name: '字幕を編集' }).click();
  await expect(page.getByRole('heading', { name: '字幕編集' })).toBeVisible();
  await expect(page.getByText(/編集済み動画へ反映するには/)).toBeVisible();
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect.poll(() => candidateSubtitleSaved).toBe(true);

  await expect(page.getByRole('link', { name: '取り込んだ元動画を保存' })).toHaveCount(0);
  await page.getByRole('button', { name: '確認して次へ' }).click();
  await page.getByRole('button', { name: '確認して次へ' }).click();
  await expect(page.getByLabel('デス', { exact: true })).toBeEmpty();
  await page.getByLabel('キル', { exact: true }).fill('3');
  await page.getByRole('button', { name: '確認して次へ' }).click();
  await page.getByRole('button', { name: '確認を終える' }).click();
  await page.getByRole('button', { name: '編集・保存する' }).click();
  await expect(page.getByRole('heading', { name: '編集結果を保存しました' })).toBeVisible();
  await expect(page.getByLabel('タイトル', { exact: true })).toHaveValue('つなげた試合');
  await expect(page.getByLabel('編集済み動画のプレビュー')).toHaveAttribute(
    'src',
    '/api/imported-videos/job-import-1/assets/output/output-1/video.mp4'
  );
  await expect(page.getByRole('link', { name: /保存/ })).toHaveCount(0);
  expect(job?.state).toBe('completed');
});
