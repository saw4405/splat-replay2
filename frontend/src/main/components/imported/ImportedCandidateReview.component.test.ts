import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import ImportedCandidateReview from './ImportedCandidateReview.svelte';
import type { ImportedBattle } from '../../api/importedVideos';

const candidate: ImportedBattle = {
  id: 'battle-1',
  start_seconds: 0,
  end_seconds: 30,
  segments: [[0, 30]],
  selected: true,
  metadata: { allies: ['旧ブキ', '', '', ''] },
  title: null,
  description: null,
  clip_ready: true,
  duration_seconds: 30,
  has_thumbnail: false,
  has_subtitle: false,
  evidence_assets: { match_select: 'match.png', result_full: 'result.png' },
  evidence_regions: {
    match_select: { match: [100, 300, 300, 80], rate: [100, 450, 200, 70] },
    result_full: { gold_medals: [880, 430, 490, 280] },
  },
};
afterEach(cleanup);

it('検出範囲で画像と対応線を切り抜き、既存リストからブキを変更する', async () => {
  const onChange = vi.fn();
  render(ImportedCandidateReview, {
    props: {
      jobId: 'job-1',
      candidate,
      patch: {},
      disabled: false,
      onChange,
      options: {
        gameModes: [],
        matches: [],
        rules: [],
        stages: [],
        judgements: [],
        weapons: [{ key: 'スシ', label: 'スプラシューター' }],
      },
    },
  });
  const match = screen.getByRole('region', { name: 'マッチ選択画面の画像と編集欄' });
  // SVG座標は画像の切り抜きと線の一致を守る表示契約。
  expect(match.querySelector('svg')).toHaveAttribute('viewBox', '0 190 1920 544.4');
  expect(within(match).getByRole('img')).toHaveStyle({
    transform: 'translateY(-17.59259259259259%)',
  });
  const result = screen.getByRole('region', { name: 'リザルト画面の画像と編集欄' });
  expect(result.querySelector('svg')).toHaveAttribute('viewBox', '0 -48 1920 806');
  const weapon = screen.getByRole('combobox', { name: '味方1のブキ' });
  expect(weapon).toHaveValue('旧ブキ');
  await userEvent.setup().selectOptions(weapon, 'スシ');
  expect(onChange).toHaveBeenCalledWith('allies', ['スシ', '', '', '']);
  expect(screen.queryByText(/イカランプは照合用/)).not.toBeInTheDocument();
  expect(screen.queryByText(/抽出区間/)).not.toBeInTheDocument();
});

it('指定した画面だけを表示し、認識座標がない画像は切り抜かない', () => {
  render(ImportedCandidateReview, {
    props: {
      jobId: 'job-1',
      candidate: { ...candidate, evidence_regions: undefined },
      options: null,
      patch: {},
      disabled: false,
      onChange: vi.fn(),
      displayedPanel: 'result_full',
    },
  });
  expect(screen.getByRole('region', { name: 'リザルト画面の画像と編集欄' })).toBeInTheDocument();
  expect(
    screen.queryByRole('region', { name: 'マッチ選択画面の画像と編集欄' })
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText('開始日時')).not.toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'リザルト画面' })).toHaveStyle({
    transform: 'translateY(0%)',
  });
});

it('画像URLがなくても読込に失敗してもメタデータを訂正できる', async () => {
  const onChange = vi.fn();
  render(ImportedCandidateReview, {
    props: {
      jobId: 'job-1',
      candidate: { ...candidate, evidence_assets: { result_full: 'broken.png' } },
      options: null,
      patch: {},
      disabled: false,
      onChange,
    },
  });
  expect(screen.getByText('マッチ選択画面の画像は未取得です。')).toBeInTheDocument();
  await fireEvent.error(screen.getByRole('img', { name: 'リザルト画面' }));
  expect(screen.getByText('リザルト画面の画像は未取得です。')).toBeInTheDocument();
  const user = userEvent.setup();
  await user.type(screen.getByRole('textbox', { name: 'レート' }), '2000');
  await user.type(screen.getByRole('spinbutton', { name: 'キル' }), '4');
  expect(onChange).toHaveBeenCalledWith('rate', '2000');
  expect(onChange).toHaveBeenCalledWith('kill', 4);
});

it('マッチの色検出点だけでもマッチ名とレートの表示文脈を含める', () => {
  render(ImportedCandidateReview, {
    props: {
      jobId: 'job-1',
      candidate: {
        ...candidate,
        evidence_regions: { match_select: { match: [280, 390, 20, 20] } },
      },
      options: null,
      patch: {},
      disabled: false,
      onChange: vi.fn(),
      displayedPanel: 'match_select',
    },
  });
  const match = screen.getByRole('region', { name: 'マッチ選択画面の画像と編集欄' });
  expect(match.querySelector('svg')).toHaveAttribute('viewBox', '0 190 1920 544.4');
  const regions = match.querySelectorAll('rect');
  expect(regions).toHaveLength(1);
  expect(Number(regions[0].getAttribute('y'))).toBeCloseTo(378.48);
  expect(Number(regions[0].getAttribute('height'))).toBeCloseTo(43.04);
  expect(screen.getByText('対応位置未取得')).toBeInTheDocument();
});

it('リザルト主要項目を画像上、共有表彰を画像下に置いて対応線を結ぶ', () => {
  render(ImportedCandidateReview, {
    props: {
      jobId: 'job-1',
      candidate: {
        ...candidate,
        evidence_regions: {
          result_full: {
            rule: [100, 100, 100, 50],
            stage: [300, 100, 100, 50],
            kill: [1300, 300, 50, 100],
            death: [1400, 300, 50, 100],
            special: [1500, 300, 50, 100],
            gold_medals: [880, 430, 490, 280],
            silver_medals: [880, 430, 490, 280],
          },
        },
      },
      options: null,
      patch: {},
      disabled: false,
      onChange: vi.fn(),
      displayedPanel: 'result_full',
    },
  });
  const image = screen.getByRole('img', { name: 'リザルト画面' });
  for (const label of ['ルール', 'ステージ', 'キル', 'デス', 'スペシャル']) {
    expect(
      screen.getByLabelText(label).compareDocumentPosition(image) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  }
  for (const label of ['金表彰', '銀表彰']) {
    expect(
      image.compareDocumentPosition(screen.getByLabelText(label)) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  }
  const result = screen.getByRole('region', { name: 'リザルト画面の画像と編集欄' });
  const lines = Array.from(result.querySelectorAll('polyline')).map((line) =>
    line.getAttribute('points')
  );
  expect(lines).toContain('150,88.48 150,-9.600000000000001 192,-48');
  expect(lines).toContain('1125,721.52 1125,721.52 480,758');
  expect(lines).toContain('1125,721.52 1125,721.52 1440,758');
  expect(within(result).getByText('3/4')).toBeInTheDocument();
});

it('表示枠だけを認識ROI外へ広げ、画像端を超えず共有枠を重ねない', () => {
  const roi: [number, number, number, number] = [0, 5, 100, 50];
  render(ImportedCandidateReview, {
    props: {
      jobId: 'job-1',
      candidate: {
        ...candidate,
        evidence_regions: {
          result_full: {
            gold_medals: roi,
            silver_medals: roi,
          },
        },
      },
      options: null,
      patch: {},
      disabled: false,
      onChange: vi.fn(),
      displayedPanel: 'result_full',
    },
  });
  const panel = screen.getByRole('region', { name: 'リザルト画面の画像と編集欄' });
  const rectangles = panel.querySelectorAll('rect');
  expect(rectangles).toHaveLength(1);
  expect(rectangles[0]).toHaveAttribute('x', '0');
  expect(rectangles[0]).toHaveAttribute('y', '0');
  expect(Number(rectangles[0].getAttribute('width'))).toBeCloseTo(111.52);
  expect(Number(rectangles[0].getAttribute('height'))).toBeCloseTo(66.52);
  expect(roi).toEqual([0, 5, 100, 50]);
});
