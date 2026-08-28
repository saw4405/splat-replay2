import { randomUUID } from 'node:crypto';
import { copyFileSync, linkSync, mkdirSync } from 'node:fs';
import { extname, join } from 'node:path';

import { expect, type Locator, type Page } from '@playwright/test';

import {
  configureReplayAsset,
  ensureE2EEnvironment,
  listReplayAssets,
  loadSidecarMetadata,
  resetE2EState,
  type E2EEnvironment,
  type ExpectedSidecarMetadata,
  type ReplayAsset,
  type ReplayScenario,
} from './e2eEnv';
import {
  seedRecordedVideos,
  type RecordedSeedSource,
  type SeededRecordedVideo,
} from './recordedSeed';

type RecordedVideoItemValues = {
  game_mode: string;
  match: string;
  rule: string;
  stage: string;
  rate: string;
  judgement: string;
  kill: string;
  death: string;
  special: string;
  gold_medals: string;
  silver_medals: string;
  allies: string[];
  enemies: string[];
};

type SidecarMetadataFields = ExpectedSidecarMetadata;

type RawMetadataOptionItem = {
  key: string;
  label: string;
};

type RawMetadataOptionsResponse = {
  game_modes: RawMetadataOptionItem[];
  matches: RawMetadataOptionItem[];
  rules: RawMetadataOptionItem[];
  stages: RawMetadataOptionItem[];
  judgements: RawMetadataOptionItem[];
};

type MetadataOptionMaps = {
  game_modes: Record<string, string>;
  matches: Record<string, string>;
  rules: Record<string, string>;
  stages: Record<string, string>;
  judgements: Record<string, string>;
};

let metadataOptionMapsPromise: Promise<MetadataOptionMaps> | null = null;
const LONG_RECORDING_TIMEOUT_MS = process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 780_000 : 420_000;

function materializeReplayAsset(environment: E2EEnvironment, asset: ReplayAsset): ReplayAsset {
  const preparedReplayDir = join(environment.rootDir, 'prepared-replays');
  const preparedVideoPath = join(
    preparedReplayDir,
    `${asset.id}-${randomUUID()}${extname(asset.videoPath)}`
  );

  mkdirSync(preparedReplayDir, { recursive: true });
  try {
    linkSync(asset.videoPath, preparedVideoPath);
  } catch {
    copyFileSync(asset.videoPath, preparedVideoPath);
  }

  return {
    ...asset,
    videoPath: preparedVideoPath,
  };
}

export async function gotoMain(page: Page): Promise<void> {
  await page.goto('/');
  await expect(page.getByTestId('settings-button')).toBeVisible();
}

function behaviorEditAfterPowerOffField(page: Page): Locator {
  return page.getByTestId('settings-field-behavior-behavior-edit_after_power_off');
}

const editAfterPowerOffLabel = '電源オフ後に編集開始する';

async function openSettings(page: Page): Promise<void> {
  await page.getByTestId('settings-button').click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeVisible();
}

async function openBehaviorSettings(page: Page): Promise<void> {
  await openSettings(page);
  await page.getByRole('radio', { name: 'すべての設定' }).click();
  await page.getByTestId('settings-section-behavior').click();
  await expect(behaviorEditAfterPowerOffField(page)).toBeVisible();
}

async function setCheckboxValue(field: Locator, label: string, checked: boolean): Promise<void> {
  const checkbox = field.getByRole('checkbox', { name: label });
  if ((await checkbox.isChecked()) !== checked) {
    await field.getByText(label, { exact: true }).click();
  }
  await expect(checkbox).toBeChecked({ checked });
}

export async function saveBehaviorSettings(page: Page): Promise<void> {
  await openBehaviorSettings(page);
  await setCheckboxValue(behaviorEditAfterPowerOffField(page), editAfterPowerOffLabel, true);
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeHidden();
}

export async function verifyPersistedBehaviorSettings(page: Page): Promise<void> {
  await openBehaviorSettings(page);
  await expect(
    behaviorEditAfterPowerOffField(page).getByRole('checkbox', {
      name: editAfterPowerOffLabel,
    })
  ).toBeChecked();
}

type AutoRecordingEnableResponse = {
  state?: string | null;
};

async function requestAutoRecordingEnable(page: Page): Promise<AutoRecordingEnableResponse> {
  const response = await page.request.post('/api/recorder/enable-auto');
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as AutoRecordingEnableResponse;
}

export async function waitForRecordingLifecycle(page: Page): Promise<void> {
  await waitForVideoPreviewReady(page);
  const recordingTrigger = page.getByRole('button', {
    name: '現在録画中です。手動録画操作を開く',
  });

  await expect
    .poll(
      async () => {
        try {
          if (await recordingTrigger.isVisible()) {
            return 'Recording';
          }
          await requestAutoRecordingEnable(page);
          return 'not_visible';
        } catch {
          await requestAutoRecordingEnable(page);
          return 'error';
        }
      },
      {
        timeout: 120_000,
        intervals: [1000],
      }
    )
    .toBe('Recording');
}

export async function ensureAutoRecordingEnabled(page: Page): Promise<void> {
  await disableAutoRecording(page);

  await expect
    .poll(
      async () => {
        const body = await requestAutoRecordingEnable(page);
        return body.state ?? 'unknown';
      },
      {
        timeout: 30_000,
        intervals: [500],
      }
    )
    .toBe('running');
}

async function recorderState(page: Page): Promise<string> {
  const response = await page.request.get('/api/recorder/state');
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { state: string };
  return body.state;
}

async function disableAutoRecording(page: Page): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await page.request.post('/api/recorder/disable-auto');
        if (!response.ok()) return 'failed';
        const body = (await response.json()) as { state?: string | null };
        return body.state ?? 'unknown';
      },
      {
        timeout: 30_000,
        intervals: [500],
      }
    )
    .toBe('stopped');
}

export async function waitForRecordingStopped(page: Page): Promise<void> {
  await expect
    .poll(() => recorderState(page), { timeout: LONG_RECORDING_TIMEOUT_MS })
    .toBe('STOPPED');
}

export async function waitForRecordedVideoReady(page: Page, expectedCount: number): Promise<void> {
  await waitForVideoPreviewReady(page);
  await waitForRecordedVideoCount(page, expectedCount);
  await expect
    .poll(() => recorderState(page), { timeout: LONG_RECORDING_TIMEOUT_MS })
    .toBe('STOPPED');
}

export async function stopRecordingForTeardown(page: Page): Promise<void> {
  try {
    if ((await recorderState(page)) !== 'STOPPED') {
      const stopResponse = await page.request.post('/api/recorder/stop');
      expect(stopResponse.ok()).toBeTruthy();
    }
  } catch (error) {
    console.warn('stopRecordingForTeardown: 停止要求を送れませんでした', error);
  }

  // STOPPED になるのをポーリングで待機
  await expect
    .poll(
      async () => {
        try {
          return await recorderState(page);
        } catch {
          return 'ERROR';
        }
      },
      {
        timeout: 10_000,
        intervals: [500],
      }
    )
    .toBe('STOPPED');

  try {
    await disableAutoRecording(page);
  } catch (error) {
    console.warn('stopRecordingForTeardown: 自動録画停止要求を送れませんでした', error);
  }
}

export async function waitForVideoPreviewReady(page: Page): Promise<void> {
  await expect
    .poll(
      async () =>
        (await page.getByTestId('video-file-preview-image').count()) +
        (await page.getByTestId('video-file-preview-surface').count()),
      {
        timeout: 120_000,
      }
    )
    .toBeGreaterThan(0);
}

export async function ensureLiveMetadataVisible(page: Page): Promise<void> {
  const killInput = page.getByLabel('キル数');
  if (await killInput.isVisible().catch(() => false)) {
    return;
  }

  await page.getByTestId('metadata-toggle-button').click();
  await expect(killInput).toBeVisible({ timeout: 10_000 });
}

export async function openRecordedVideos(page: Page): Promise<void> {
  const recordedVideoList = page.getByTestId('recorded-video-list');
  if (await recordedVideoList.isVisible().catch(() => false)) {
    return;
  }
  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(recordedVideoList).toBeVisible();
}

export async function firstRecordedVideo(page: Page): Promise<Locator> {
  const item = page.getByTestId('recorded-video-item').first();
  await expect(item).toBeVisible({ timeout: 120_000 });
  return item;
}

export async function waitForRecordedVideoCount(page: Page, expectedCount: number): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await page.request.get('/api/assets/recorded');
        expect(response.ok()).toBeTruthy();
        const body = (await response.json()) as Array<{ id: string }>;
        return body.length;
      },
      {
        timeout: LONG_RECORDING_TIMEOUT_MS,
      }
    )
    .toBe(expectedCount);
}

function normalizeText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, ' ').trim() ?? '';
}

function toOptionMap(items: RawMetadataOptionItem[] | undefined): Record<string, string> {
  return (items ?? []).reduce<Record<string, string>>((map, item) => {
    map[item.key] = item.label;
    return map;
  }, {});
}

async function getMetadataOptionMaps(page: Page): Promise<MetadataOptionMaps> {
  if (!metadataOptionMapsPromise) {
    metadataOptionMapsPromise = (async () => {
      const response = await page.request.get('/api/metadata/options');
      expect(response.ok()).toBeTruthy();
      const body = (await response.json()) as RawMetadataOptionsResponse;
      return {
        game_modes: toOptionMap(body.game_modes),
        matches: toOptionMap(body.matches),
        rules: toOptionMap(body.rules),
        stages: toOptionMap(body.stages),
        judgements: toOptionMap(body.judgements),
      };
    })();
  }
  return metadataOptionMapsPromise;
}

function formatEnumLabel(
  value: string | null | undefined,
  map: Record<string, string>,
  fallback: string
): string {
  if (!value) {
    return fallback;
  }
  return map[value] ?? value;
}

function formatRate(value: string | null | undefined): string {
  const normalized = normalizeText(value);
  return normalized || '未検出';
}

function formatNumber(value: number | null | undefined): string {
  return value === null || typeof value === 'undefined' ? '0' : String(value);
}

function formatWeaponSlots(value: string[] | null | undefined): string[] {
  const slots = Array.isArray(value) ? value : [];
  const normalized = slots.slice(0, 4).map((weapon) => normalizeText(weapon) || '不明');
  while (normalized.length < 4) {
    normalized.push('不明');
  }
  return normalized;
}

function parseWeaponSlots(value: string): string[] {
  const slots = value
    .split(/\r?\n|,/)
    .map((weapon) => normalizeText(weapon))
    .filter((weapon) => weapon.length > 0);
  while (slots.length < 4) {
    slots.push('不明');
  }
  return slots.slice(0, 4);
}

function expectRecognizedWeaponSlots(value: string[], fieldName: string): void {
  expect(value, `${fieldName} は 4 スロットである必要があります`).toHaveLength(4);
  for (const weapon of value) {
    expect(
      weapon,
      `${fieldName} には分類結果が表示され、空値やプレースホルダだけで終わらない必要があります`
    ).not.toMatch(/^(|不明)$/);
  }
}

async function readTestIdText(item: Locator, testId: string): Promise<string> {
  return normalizeText(await item.getByTestId(testId).textContent());
}

async function readTestIdRawText(item: Locator, testId: string): Promise<string> {
  return (await item.getByTestId(testId).textContent()) ?? '';
}

async function expectedRecordedVideoValues(
  page: Page,
  expected: SidecarMetadataFields
): Promise<RecordedVideoItemValues> {
  const optionMaps = await getMetadataOptionMaps(page);
  return {
    game_mode: formatEnumLabel(expected.game_mode, optionMaps.game_modes, '未取得'),
    match: formatEnumLabel(expected.match, optionMaps.matches, '未取得'),
    rule: formatEnumLabel(expected.rule, optionMaps.rules, '未取得'),
    stage: formatEnumLabel(expected.stage, optionMaps.stages, '未取得'),
    rate: formatRate(expected.rate),
    judgement: formatEnumLabel(expected.judgement, optionMaps.judgements, '未判定'),
    kill: formatNumber(expected.kill),
    death: formatNumber(expected.death),
    special: formatNumber(expected.special),
    gold_medals: formatNumber(expected.gold_medals),
    silver_medals: formatNumber(expected.silver_medals),
    allies: formatWeaponSlots(expected.allies),
    enemies: formatWeaponSlots(expected.enemies),
  };
}

export function environment(): E2EEnvironment {
  return ensureE2EEnvironment();
}

export function replayAssets(environment: E2EEnvironment): ReplayAsset[] {
  return environment.replayAssets;
}

export function expectedRecordedVideoCount(asset: ReplayAsset): number {
  return loadSidecarMetadata(asset)?.scenario?.expected_recorded_count ?? 1;
}

export function recordableReplayAssets(environment: E2EEnvironment): ReplayAsset[] {
  const assets = listReplayAssets(environment.autoRecordingReplayDir).filter(
    (asset) => expectedRecordedVideoCount(asset) > 0
  );
  return environment.mode === 'smoke' ? assets.slice(0, 1) : assets;
}

export function resetReplayTestState(environment: E2EEnvironment): void {
  resetE2EState(environment);
}

export function prepareReplayAsset(environment: E2EEnvironment, asset: ReplayAsset): void {
  resetE2EState(environment);
  configureReplayAsset(environment, materializeReplayAsset(environment, asset));
}

export function prepareReplayAssetWithScenario(
  environment: E2EEnvironment,
  asset: ReplayAsset,
  scenarioOverride: ReplayScenario
): void {
  resetE2EState(environment);
  configureReplayAsset(environment, materializeReplayAsset(environment, asset), scenarioOverride);
}

export function switchReplayAsset(environment: E2EEnvironment, asset: ReplayAsset): void {
  configureReplayAsset(environment, materializeReplayAsset(environment, asset));
}

export function prepareRecordedSeedAssets(
  environment: E2EEnvironment,
  sources: RecordedSeedSource[]
): SeededRecordedVideo[] {
  resetE2EState(environment);
  return seedRecordedVideos(environment, sources);
}

export function prepareRecordedSeedAsset(
  environment: E2EEnvironment,
  source: RecordedSeedSource
): SeededRecordedVideo {
  const [seeded] = prepareRecordedSeedAssets(environment, [source]);
  return seeded;
}

export function expectedSidecarMetadata(asset: ReplayAsset): SidecarMetadataFields | null {
  return loadSidecarMetadata(asset)?.expected ?? null;
}

export async function readRecordedVideoItemValues(item: Locator): Promise<RecordedVideoItemValues> {
  return {
    game_mode: await readTestIdText(item, 'recorded-video-game-mode'),
    match: await readTestIdText(item, 'recorded-video-match'),
    rule: await readTestIdText(item, 'recorded-video-rule'),
    stage: await readTestIdText(item, 'recorded-video-stage'),
    rate: await readTestIdText(item, 'recorded-video-rate'),
    judgement: await readTestIdText(item, 'recorded-video-judgement'),
    kill: await readTestIdText(item, 'recorded-video-kill'),
    death: await readTestIdText(item, 'recorded-video-death'),
    special: await readTestIdText(item, 'recorded-video-special'),
    gold_medals: await readTestIdText(item, 'recorded-video-gold-medals'),
    silver_medals: await readTestIdText(item, 'recorded-video-silver-medals'),
    allies: parseWeaponSlots(await readTestIdRawText(item, 'recorded-video-allies')),
    enemies: parseWeaponSlots(await readTestIdRawText(item, 'recorded-video-enemies')),
  };
}

export async function expectSidecarToMatchRecordedVideoItem(
  page: Page,
  item: Locator,
  expected: SidecarMetadataFields | null
): Promise<void> {
  if (!expected) {
    return;
  }

  const expectedValues = await expectedRecordedVideoValues(page, expected);
  const displayWait = { timeout: 30_000 };

  await expect(item.getByTestId('recorded-video-game-mode')).toHaveText(
    expectedValues.game_mode,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-match')).toHaveText(
    expectedValues.match,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-rule')).toHaveText(
    expectedValues.rule,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-stage')).toHaveText(
    expectedValues.stage,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-rate')).toHaveText(
    expectedValues.rate,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-judgement')).toHaveText(
    expectedValues.judgement,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-kill')).toHaveText(
    expectedValues.kill,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-death')).toHaveText(
    expectedValues.death,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-special')).toHaveText(
    expectedValues.special,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-gold-medals')).toHaveText(
    expectedValues.gold_medals,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-silver-medals')).toHaveText(
    expectedValues.silver_medals,
    displayWait
  );
  await expect(item.getByTestId('recorded-video-allies')).toBeVisible(displayWait);
  await expect(item.getByTestId('recorded-video-enemies')).toBeVisible(displayWait);

  const actualValues = await readRecordedVideoItemValues(item);
  expect(actualValues.game_mode).toBe(expectedValues.game_mode);
  expect(actualValues.match).toBe(expectedValues.match);
  expect(actualValues.rule).toBe(expectedValues.rule);
  expect(actualValues.stage).toBe(expectedValues.stage);
  expect(actualValues.rate).toBe(expectedValues.rate);
  expect(actualValues.judgement).toBe(expectedValues.judgement);
  expect(actualValues.kill).toBe(expectedValues.kill);
  expect(actualValues.death).toBe(expectedValues.death);
  expect(actualValues.special).toBe(expectedValues.special);
  expect(actualValues.gold_medals).toBe(expectedValues.gold_medals);
  expect(actualValues.silver_medals).toBe(expectedValues.silver_medals);
  // observations は replay 入力、expected は UI の独立期待値であるため、
  // 保存後の武器 slot 順・値が両者を正しくつないだ結果かをここで確認する。
  expect(actualValues.allies).toEqual(expectedValues.allies);
  expect(actualValues.enemies).toEqual(expectedValues.enemies);
  expectRecognizedWeaponSlots(actualValues.allies, '味方武器');
  expectRecognizedWeaponSlots(actualValues.enemies, '相手武器');
}
