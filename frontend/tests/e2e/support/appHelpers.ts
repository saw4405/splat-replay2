import { expect, type Locator, type Page } from '@playwright/test';

import {
  configureReplayAsset,
  ensureE2EEnvironment,
  loadSidecarMetadata,
  resetE2EState,
  type E2EEnvironment,
  type ReplayAsset,
} from './e2eEnv';

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

export async function waitForRecordingLifecycle(page: Page): Promise<void> {
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
  await expect(page.getByTestId('video-preview-status')).toHaveText('Recording', {
    timeout: 120_000,
  });
}

export async function openRecordedVideos(page: Page): Promise<void> {
  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(page.getByTestId('recorded-video-list')).toBeVisible();
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

export function resetReplayTestState(environment: E2EEnvironment): void {
  resetE2EState(environment);
}

export function prepareReplayAsset(environment: E2EEnvironment, asset: ReplayAsset): void {
  resetE2EState(environment);
  configureReplayAsset(environment, asset);
}

export function expectedSidecarMetadata(asset: ReplayAsset) {
  return loadSidecarMetadata(asset);
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
