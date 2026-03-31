import { randomUUID } from 'node:crypto';
import { copyFileSync, linkSync, mkdirSync } from 'node:fs';
import { extname, join } from 'node:path';

import { expect, type Locator, type Page } from '@playwright/test';

import {
  configureReplayAsset,
  ensureE2EEnvironment,
  loadSidecarMetadata,
  resetE2EState,
  type E2EEnvironment,
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

type SidecarMetadataFields = Omit<NonNullable<ReturnType<typeof loadSidecarMetadata>>, 'scenario'>;

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

async function openSettings(page: Page): Promise<void> {
  await page.getByTestId('settings-button').click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeVisible();
}

async function openBehaviorSettings(page: Page): Promise<void> {
  await openSettings(page);
  await page.getByTestId('settings-section-behavior').click();
  await expect(behaviorEditAfterPowerOffField(page)).toBeVisible();
}

async function setCheckboxValue(checkbox: Locator, checked: boolean): Promise<void> {
  if ((await checkbox.isChecked()) === checked) {
    return;
  }
  await checkbox.evaluate((element, nextChecked) => {
    const input = element as HTMLInputElement;
    input.checked = nextChecked;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, checked);
}

export async function saveBehaviorSettings(page: Page): Promise<void> {
  await openBehaviorSettings(page);
  await setCheckboxValue(
    behaviorEditAfterPowerOffField(page).locator('input[type="checkbox"]'),
    true
  );
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeHidden();
}

export async function verifyPersistedBehaviorSettings(page: Page): Promise<void> {
  await openBehaviorSettings(page);
  await expect(
    behaviorEditAfterPowerOffField(page).locator('input[type="checkbox"]')
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
  const statusLabel = page.getByTestId('video-preview-status');
  const deadline = Date.now() + 120_000;
  let lastStatus = 'unknown';

  while (Date.now() < deadline) {
    try {
      await expect(statusLabel).toHaveText('Recording', {
        timeout: 5_000,
      });
      return;
    } catch {
      lastStatus = (await statusLabel.textContent().catch(() => null))?.trim() ?? 'unknown';
    }

    await requestAutoRecordingEnable(page);
    await page.waitForTimeout(1_000);
  }

  throw new Error(`録画開始を待機中にタイムアウトしました。最後の表示状態: ${lastStatus}`);
}

export async function ensureAutoRecordingEnabled(page: Page): Promise<void> {
  await disableAutoRecording(page);

  const deadline = Date.now() + 30_000;
  let lastState = 'unknown';

  while (Date.now() < deadline) {
    const body = await requestAutoRecordingEnable(page);
    lastState = body.state ?? 'unknown';
    if (lastState === 'running') {
      return;
    }
    await page.waitForTimeout(500);
  }

  throw new Error(`自動録画を有効化できませんでした。最後の state: ${lastState}`);
}

async function recorderState(page: Page): Promise<string> {
  const response = await page.request.get('/api/recorder/state');
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { state: string };
  return body.state;
}

async function disableAutoRecording(page: Page): Promise<void> {
  const deadline = Date.now() + 30_000;
  let lastState = 'unknown';

  while (Date.now() < deadline) {
    const response = await page.request.post('/api/recorder/disable-auto');
    expect(response.ok()).toBeTruthy();
    const body = (await response.json()) as { state?: string | null };
    lastState = body.state ?? 'unknown';
    if (lastState === 'stopped') {
      return;
    }
    await page.waitForTimeout(500);
  }

  throw new Error(`自動録画を停止できませんでした。最後の state: ${lastState}`);
}

export async function waitForRecordingStopped(page: Page): Promise<void> {
  await expect(page.getByTestId('video-preview-status')).toHaveText('Stopped', {
    timeout: LONG_RECORDING_TIMEOUT_MS,
  });
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

  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      if ((await recorderState(page)) === 'STOPPED') {
        await page.waitForTimeout(3_000);
        return;
      }
    } catch {
      // backend 切り替え中の一時失敗は cleanup では許容する
    }
    await page.waitForTimeout(500);
  }

  try {
    await disableAutoRecording(page);
  } catch (error) {
    console.warn('stopRecordingForTeardown: 自動録画停止要求を送れませんでした', error);
  }

  await page.waitForTimeout(1_000);
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
  const slots = value.split(',').map((weapon) => normalizeText(weapon) || '不明');
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

async function expectedRecordedVideoValues(
  page: Page,
  expected: NonNullable<ReturnType<typeof loadSidecarMetadata>>
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
  return environment.replayAssets.filter((asset) => expectedRecordedVideoCount(asset) > 0);
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

export function expectedSidecarMetadata(asset: ReplayAsset) {
  const sidecar = loadSidecarMetadata(asset);
  if (!sidecar) {
    return null;
  }

  const { scenario: _scenario, ...metadata } = sidecar;
  const hasExpectedMetadata = Object.values(metadata).some(
    (value) => value !== null && typeof value !== 'undefined'
  );
  if (!hasExpectedMetadata) {
    return null;
  }
  return metadata as SidecarMetadataFields;
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
    allies: parseWeaponSlots(await readTestIdText(item, 'recorded-video-allies')),
    enemies: parseWeaponSlots(await readTestIdText(item, 'recorded-video-enemies')),
  };
}

export async function expectSidecarToMatchRecordedVideoItem(
  page: Page,
  item: Locator,
  expected: ReturnType<typeof loadSidecarMetadata>
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
  // exact な武器識別は backend の認識器テストで担保し、workflow E2E では
  // 録画保存後に UI へ有効な武器情報が表示されることを確認する。
  expectRecognizedWeaponSlots(actualValues.allies, '味方武器');
  expectRecognizedWeaponSlots(actualValues.enemies, '相手武器');
}
