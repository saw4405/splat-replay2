# E2E Replay Usage Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** E2E 全体で battle replay 動画を使う範囲を「自動録画制御」と「録画中操作」に限定し、録画済み前提の spec は seed 化したうえで重複 spec を整理する。

**Architecture:** replay fixture から recorded asset を直接 `storage/recorded` へ配置する filesystem seed helper を追加し、録画済み前提の spec は `/api/recorder/enable-auto` を踏まない構成へ置き換える。`error-recovery.spec.ts` は Playwright の isolation 原則に沿って live / recorded / settings の 3 spec に分割し、録画中前提だけ replay を残す。

**Tech Stack:** TypeScript, Playwright E2E, Vitest, Node.js `fs` / `path`, Markdown documentation

---

## File Structure

- `frontend/tests/e2e/support/recordedSeed.ts`
  - replay fixture を recorded asset として seed する pure filesystem helper。
- `frontend/src/recordedSeed.test.ts`
  - seed helper が `recorded/` 配下へ動画と sidecar を正しく配置できることを Vitest で担保する。
- `frontend/tests/e2e/support/appHelpers.ts`
  - spec から使う `prepareRecordedSeedAsset(s)` を公開する。
- `frontend/tests/e2e/edit-upload-workflow.spec.ts`
  - 録画済み 1 件前提へ変更し、replay 再生禁止ガードを追加する。
- `frontend/tests/e2e/multi-video-management.spec.ts`
  - 録画済み 2 件前提へ変更し、重複している独立性確認を 1 本へ整理する。
- `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`
  - 録画済み 1 件前提へ変更し、成功系を代表保存 / キャンセル / 再オープン確認へ圧縮する。
- `frontend/tests/e2e/error-recovery-recording-live.spec.ts`
  - replay を残す録画中エラー復旧だけを保持する。
- `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`
  - seed 前提の録画済み asset エラー復旧だけを保持する。
- `frontend/tests/e2e/error-recovery-settings.spec.ts`
  - 動画不要の設定保存失敗だけを保持する。
- `frontend/tests/e2e/error-recovery.spec.ts`
  - 削除する。前提状態が混在しており、今回の責務分離と相反するため。
- `docs/e2e_replay_test.md`
  - replay を使う spec / seed 化した spec / 動画不要 spec の分類、実行入口、保守方針を更新する。

### Task 1: recorded seed helper を追加する

**Files:**
- Create: `frontend/src/recordedSeed.test.ts`
- Create: `frontend/tests/e2e/support/recordedSeed.ts`
- Modify: `frontend/tests/e2e/support/appHelpers.ts`
- Test: `frontend/src/recordedSeed.test.ts`

- [ ] **Step 1: seed helper の失敗テストを書く**

Create: `frontend/src/recordedSeed.test.ts`

```ts
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { bootstrapE2EEnvironment } from '../tests/e2e/support/e2eEnv';
import { seedRecordedVideos } from '../tests/e2e/support/recordedSeed';

const temporaryRoots: string[] = [];

function bootEnvironment() {
  const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-recorded-seed-'));
  temporaryRoots.push(rootDir);

  vi.stubEnv('SPLAT_REPLAY_E2E_ROOT', rootDir);
  vi.stubEnv('SPLAT_REPLAY_SETTINGS_FILE', join(rootDir, 'settings.toml'));
  vi.stubEnv('SPLAT_REPLAY_E2E_MODE', 'smoke');

  return bootstrapE2EEnvironment(true);
}

describe('recorded seed helper', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    while (temporaryRoots.length > 0) {
      const root = temporaryRoots.pop();
      if (!root) {
        continue;
      }
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('copies replay asset into recorded storage with metadata json', () => {
    const environment = bootEnvironment();
    const asset = environment.replayAssets[0];

    const [seeded] = seedRecordedVideos(environment, [{ asset }]);
    const metadata = JSON.parse(readFileSync(seeded.metadataPath, 'utf-8')) as {
      game_mode?: string;
      scenario?: unknown;
    };

    expect(existsSync(seeded.videoPath)).toBe(true);
    expect(metadata.game_mode).toBe('BATTLE');
    expect(metadata.scenario).toBeUndefined();
  });

  it('supports duplicate seeds with file stem and metadata overrides', () => {
    const environment = bootEnvironment();
    const asset = environment.replayAssets[0];

    seedRecordedVideos(environment, [
      { asset, fileStem: '20260312_222200_regular_first' },
      {
        asset,
        fileStem: '20260312_222201_regular_second',
        metadataOverride: {
          started_at: '2026-03-12T22:22:01.999005',
          kill: 21,
        },
      },
    ]);

    const secondMetadata = JSON.parse(
      readFileSync(
        join(
          environment.storageDir,
          'recorded',
          '20260312_222201_regular_second.json'
        ),
        'utf-8'
      )
    ) as {
      started_at?: string;
      kill?: number;
    };

    expect(secondMetadata.started_at).toBe('2026-03-12T22:22:01.999005');
    expect(secondMetadata.kill).toBe(21);
  });
});
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd frontend && npm run test -- src/recordedSeed.test.ts`

Expected: `Cannot find module '../tests/e2e/support/recordedSeed'` で FAIL する。

- [ ] **Step 3: 最小実装を書く**

Create: `frontend/tests/e2e/support/recordedSeed.ts`

```ts
import { copyFileSync, linkSync, mkdirSync, writeFileSync } from 'node:fs';
import { extname, join } from 'node:path';

import {
  loadSidecarMetadata,
  type E2EEnvironment,
  type ReplayAsset,
  type SidecarMetadata,
} from './e2eEnv';

export type RecordedSeedMetadata = Omit<SidecarMetadata, 'scenario'>;

export type RecordedSeedSource = {
  asset: ReplayAsset;
  fileStem?: string;
  metadataOverride?: Partial<RecordedSeedMetadata>;
};

export type SeededRecordedVideo = {
  videoPath: string;
  metadataPath: string;
};

function linkOrCopy(source: string, destination: string): void {
  try {
    linkSync(source, destination);
  } catch {
    copyFileSync(source, destination);
  }
}

function buildRecordedMetadata(source: RecordedSeedSource): RecordedSeedMetadata {
  const sidecar = loadSidecarMetadata(source.asset);
  if (!sidecar) {
    throw new Error(`Recorded seed requires sidecar metadata: ${source.asset.name}`);
  }

  const { scenario: _scenario, ...metadata } = sidecar;
  return {
    ...metadata,
    ...source.metadataOverride,
  };
}

export function seedRecordedVideos(
  environment: E2EEnvironment,
  sources: RecordedSeedSource[]
): SeededRecordedVideo[] {
  const recordedDir = join(environment.storageDir, 'recorded');
  mkdirSync(recordedDir, { recursive: true });

  return sources.map((source, index) => {
    const fileStem = source.fileStem ?? `${source.asset.id}-seed-${index + 1}`;
    const videoPath = join(recordedDir, `${fileStem}${extname(source.asset.videoPath)}`);
    const metadataPath = join(recordedDir, `${fileStem}.json`);

    linkOrCopy(source.asset.videoPath, videoPath);
    writeFileSync(
      metadataPath,
      JSON.stringify(buildRecordedMetadata(source), null, 2),
      'utf-8'
    );

    return {
      videoPath,
      metadataPath,
    };
  });
}
```

Modify: `frontend/tests/e2e/support/appHelpers.ts`

```ts
import {
  seedRecordedVideos,
  type RecordedSeedSource,
} from './recordedSeed';
```

```ts
export function prepareRecordedSeedAsset(
  environment: E2EEnvironment,
  asset: ReplayAsset
): void {
  resetE2EState(environment);
  seedRecordedVideos(environment, [{ asset }]);
}

export function prepareRecordedSeedAssets(
  environment: E2EEnvironment,
  sources: RecordedSeedSource[]
): void {
  resetE2EState(environment);
  seedRecordedVideos(environment, sources);
}
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd frontend && npm run test -- src/recordedSeed.test.ts`

Expected: `2 passed`

- [ ] **Step 5: コミットする**

```bash
git add frontend/src/recordedSeed.test.ts frontend/tests/e2e/support/recordedSeed.ts frontend/tests/e2e/support/appHelpers.ts
git commit -m "test: add recorded seed helper for e2e"
```

### Task 2: edit-upload workflow を seed 化する

**Files:**
- Modify: `frontend/tests/e2e/edit-upload-workflow.spec.ts`
- Test: `frontend/tests/e2e/edit-upload-workflow.spec.ts`

- [ ] **Step 1: replay 再生禁止ガードを先に入れる**

Modify: `frontend/tests/e2e/edit-upload-workflow.spec.ts`

```ts
let autoEnableRequestCount = 0;

test.beforeEach(async ({ page }) => {
  autoEnableRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    autoEnableRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(autoEnableRequestCount).toBe(0);
});
```

- [ ] **Step 2: 旧実装では guard が失敗することを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts`

Expected: `Expected: 0` / `Received: 1` で FAIL する。

- [ ] **Step 3: 録画済み seed 前提へ置き換える**

Replace the import block and setup in `frontend/tests/e2e/edit-upload-workflow.spec.ts` with:

```ts
import { expect, test } from '@playwright/test';

import {
  environment,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAsset,
  recordableReplayAssets,
} from './support/appHelpers';

const e2eEnvironment = environment();
const firstSeedAsset = recordableReplayAssets(e2eEnvironment)[0];
let autoEnableRequestCount = 0;

test.beforeAll(async ({ request }) => {
  await request.post('/api/settings/youtube-permission-dialog', {
    data: { shown: true },
  });
});

test.beforeEach(async ({ page }) => {
  autoEnableRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    autoEnableRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(autoEnableRequestCount).toBe(0);
});
```

Replace each replay bootstrap block:

```ts
if (!firstSeedAsset) {
  test.skip();
  return;
}

prepareRecordedSeedAsset(e2eEnvironment, firstSeedAsset);

await gotoMain(page);
await openRecordedVideos(page);
await expect(page.getByTestId('recorded-count')).toHaveText('1', {
  timeout: 30_000,
});
```

Delete the old calls to `prepareReplayAsset()`, `ensureAutoRecordingEnabled()`, and `waitForRecordedVideoReady()` from both tests.

- [ ] **Step 4: spec が通ることを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts`

Expected: `2 passed`

- [ ] **Step 5: コミットする**

```bash
git add frontend/tests/e2e/edit-upload-workflow.spec.ts
git commit -m "test: seed edit upload e2e workflow"
```

### Task 3: multi-video management を seed 化し、重複ケースを削る

**Files:**
- Modify: `frontend/tests/e2e/multi-video-management.spec.ts`
- Test: `frontend/tests/e2e/multi-video-management.spec.ts`

- [ ] **Step 1: replay 再生禁止ガードを追加する**

Modify: `frontend/tests/e2e/multi-video-management.spec.ts`

```ts
let autoEnableRequestCount = 0;

test.beforeEach(async ({ page }) => {
  autoEnableRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    autoEnableRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(autoEnableRequestCount).toBe(0);
});
```

- [ ] **Step 2: 旧実装では guard が失敗することを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/multi-video-management.spec.ts`

Expected: `Expected: 0` / `Received: 2` 以上で FAIL する。

- [ ] **Step 3: 2 本の recorded seed へ置き換え、独立性の重複 1 本を削除する**

Add this helper block to `frontend/tests/e2e/multi-video-management.spec.ts`:

```ts
import type { Page } from '@playwright/test';
```

```ts
import {
  environment,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAssets,
  recordableReplayAssets,
  resetReplayTestState,
  waitForRecordedVideoCount,
} from './support/appHelpers';
```

```ts
const e2eEnvironment = environment();
const primarySeedAsset = recordableReplayAssets(e2eEnvironment)[0];
let autoEnableRequestCount = 0;

function seedMultiVideoAssets(): boolean {
  if (!primarySeedAsset) {
    return false;
  }

  prepareRecordedSeedAssets(e2eEnvironment, [
    { asset: primarySeedAsset, fileStem: '20260312_222200_regular_first' },
    {
      asset: primarySeedAsset,
      fileStem: '20260312_222201_regular_second',
      metadataOverride: {
        started_at: '2026-03-12T22:22:01.999005',
        kill: 7,
        death: 5,
        special: 2,
      },
    },
  ]);

  return true;
}

async function openSeededMultiVideoList(page: Page): Promise<void> {
  await gotoMain(page);
  await openRecordedVideos(page);
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(2);
}
```

Replace the setup phase of all non-empty tests with:

```ts
if (!seedMultiVideoAssets()) {
  test.skip();
  return;
}

await openSeededMultiVideoList(page);
```

Replace the empty-state test setup with:

```ts
resetReplayTestState(e2eEnvironment);

await gotoMain(page);
await page.getByTestId('bottom-drawer-toggle').click();
await expect(page.getByTestId('recorded-video-list')).toBeVisible();
await expect(page.getByTestId('recorded-count')).toHaveText('0', {
  timeout: 10_000,
});
await expect(page.getByTestId('recorded-video-item')).toHaveCount(0);
```

Keep exactly one edit-independence test and remove the duplicate block named:

```ts
test('複数ビデオ一覧ワークフロー - ビデオごとに独立したメタデータ状態', async ({ page }) => {
```

Retain the stronger second-item edit test, using this assertion body:

```ts
const videoItems = page.getByTestId('recorded-video-item');
const firstVideo = videoItems.first();
const secondVideo = videoItems.nth(1);
const firstKillBefore = (
  await firstVideo.getByTestId('recorded-video-kill').textContent()
)?.trim();
const secondKillBefore = (
  await secondVideo.getByTestId('recorded-video-kill').textContent()
)?.trim();

await secondVideo.getByTestId('recorded-video-metadata-button').click();
await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
  timeout: 10_000,
});

const newKillValue = String(Number.parseInt(secondKillBefore ?? '0', 10) + 7);
await page.getByLabel('キル数').fill(newKillValue);
await page.getByRole('button', { name: '保存' }).click();
await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
  timeout: 10_000,
});

const firstKillAfter = (
  await page
    .getByTestId('recorded-video-item')
    .first()
    .getByTestId('recorded-video-kill')
    .textContent()
)?.trim();
const secondKillAfter = (
  await page
    .getByTestId('recorded-video-item')
    .nth(1)
    .getByTestId('recorded-video-kill')
    .textContent()
)?.trim();

expect(firstKillAfter).toBe(firstKillBefore);
expect(secondKillAfter).toBe(newKillValue);
```

- [ ] **Step 4: spec が通ることを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/multi-video-management.spec.ts`

Expected: `6 passed`

- [ ] **Step 5: コミットする**

```bash
git add frontend/tests/e2e/multi-video-management.spec.ts
git commit -m "test: seed multi video management e2e"
```

### Task 4: recorded metadata workflow を seed 化し、成功系を 3 本へ圧縮する

**Files:**
- Modify: `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`
- Test: `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`

- [ ] **Step 1: replay 再生禁止ガードを追加する**

Modify: `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`

```ts
let autoEnableRequestCount = 0;

test.beforeEach(async ({ page }) => {
  autoEnableRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    autoEnableRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(autoEnableRequestCount).toBe(0);
});
```

- [ ] **Step 2: 旧実装では guard が失敗することを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/recorded-metadata-edit-workflow.spec.ts`

Expected: `Expected: 0` / `Received: 1` で FAIL する。

- [ ] **Step 3: seed 前提へ置き換え、代表保存 / キャンセル / 再オープン確認へ圧縮する**

Replace the import block and setup with:

```ts
import type { Page } from '@playwright/test';
import { expect, test } from '@playwright/test';

import {
  environment,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAsset,
  recordableReplayAssets,
} from './support/appHelpers';

const e2eEnvironment = environment();
const firstSeedAsset = recordableReplayAssets(e2eEnvironment)[0];
let autoEnableRequestCount = 0;

async function openSeededRecordedVideo(page: Page) {
  if (!firstSeedAsset) {
    test.skip();
    return null;
  }

  prepareRecordedSeedAsset(e2eEnvironment, firstSeedAsset);
  await gotoMain(page);
  await openRecordedVideos(page);
  return firstRecordedVideo(page);
}
```

Keep exactly these three tests:

```ts
test('録画済みメタデータ編集 - 代表保存', async ({ page }) => {
  const recordedVideo = await openSeededRecordedVideo(page);
  if (!recordedVideo) {
    return;
  }

  await recordedVideo.getByTestId('recorded-video-metadata-button').click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  await page.getByLabel('キル数').fill('20');
  await page.getByLabel('デス数').fill('4');

  const ruleSelect = page.getByLabel('ルール');
  const initialRuleValue = await ruleSelect.inputValue();
  const options = await ruleSelect.locator('option').all();
  let nextRuleValue: string | null = null;

  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value && value !== initialRuleValue && value !== '') {
      nextRuleValue = value;
      break;
    }
  }

  expect(nextRuleValue).not.toBeNull();
  await ruleSelect.selectOption(nextRuleValue!);
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  const updatedRecordedVideo = await firstRecordedVideo(page);
  await expect(updatedRecordedVideo.getByTestId('recorded-video-kill')).toHaveText('20');
  await expect(updatedRecordedVideo.getByTestId('recorded-video-death')).toHaveText('4');
  await expect(updatedRecordedVideo.getByTestId('recorded-video-rule')).not.toHaveText('');
});

test('録画済みメタデータ編集 - キャンセル', async ({ page }) => {
  const recordedVideo = await openSeededRecordedVideo(page);
  if (!recordedVideo) {
    return;
  }

  const initialKill = await recordedVideo.getByTestId('recorded-video-kill').textContent();
  await recordedVideo.getByTestId('recorded-video-metadata-button').click();
  await page.getByLabel('キル数').fill('99');
  await page.getByRole('button', { name: 'キャンセル' }).click();

  const updatedRecordedVideo = await firstRecordedVideo(page);
  const displayedKill = await updatedRecordedVideo.getByTestId('recorded-video-kill').textContent();
  expect(displayedKill?.trim()).toBe(initialKill?.trim());
});

test('録画済みメタデータ編集 - 保存値を再オープンで引き継ぐ', async ({ page }) => {
  const recordedVideo = await openSeededRecordedVideo(page);
  if (!recordedVideo) {
    return;
  }

  await recordedVideo.getByTestId('recorded-video-metadata-button').click();
  await page.getByLabel('キル数').fill('22');
  await page.getByRole('button', { name: '保存' }).click();

  const updatedRecordedVideo = await firstRecordedVideo(page);
  await updatedRecordedVideo.getByTestId('recorded-video-metadata-button').click();
  await expect(page.getByLabel('キル数')).toHaveValue('22');
  await page.getByRole('button', { name: 'キャンセル' }).click();
});
```

Delete the old field-specific success blocks that overlap with the three cases above.

- [ ] **Step 4: spec が通ることを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/recorded-metadata-edit-workflow.spec.ts`

Expected: `3 passed`

- [ ] **Step 5: コミットする**

```bash
git add frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts
git commit -m "test: seed recorded metadata e2e"
```

### Task 5: error-recovery を live / recorded / settings に分割する

**Files:**
- Create: `frontend/tests/e2e/error-recovery-recording-live.spec.ts`
- Create: `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`
- Create: `frontend/tests/e2e/error-recovery-settings.spec.ts`
- Delete: `frontend/tests/e2e/error-recovery.spec.ts`
- Test: `frontend/tests/e2e/error-recovery-recording-live.spec.ts`
- Test: `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`
- Test: `frontend/tests/e2e/error-recovery-settings.spec.ts`

- [ ] **Step 1: 新 spec の実行入口を先に固定する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/error-recovery-recording-live.spec.ts`

Expected: `No tests found` で FAIL する。

- [ ] **Step 2: live / recorded / settings の 3 spec を作り、旧 spec を削除する**

Create: `frontend/tests/e2e/error-recovery-recording-live.spec.ts`

```ts
import { expect, test } from '@playwright/test';

import {
  ensureAutoRecordingEnabled,
  ensureLiveMetadataVisible,
  environment,
  gotoMain,
  prepareReplayAssetWithScenario,
  replayAssets,
  stopRecordingForTeardown,
  waitForRecordingLifecycle,
} from './support/appHelpers';

const e2eEnvironment = environment();
const firstAsset = replayAssets(e2eEnvironment)[0];
const liveRecordingBootstrapScenario = {
  replay_bootstrap: {
    phase: 'in_game',
    game_mode: 'BATTLE',
  },
};

test('エラー復旧 - メタデータオプション読み込み失敗時のフォールバック', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);
  await page.route('**/api/metadata/options', (route) => {
    route.abort('failed');
  });

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  const killInput = page.getByLabel('キル数');
  await expect(killInput).toBeVisible();
  await killInput.fill('10');
  await expect(killInput).toHaveValue('10');

  await stopRecordingForTeardown(page);
  await page.unroute('**/api/metadata/options');
});

test('エラー復旧 - 録画中メタデータ保存失敗後に再保存できる', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  const killInput = page.getByLabel('キル数');
  await killInput.fill('15');

  await page.route('**/api/recorder/metadata', (route) => {
    if (route.request().method() === 'PATCH') {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
      return;
    }
    route.continue();
  });

  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();
  await expect(page.getByText('メタデータの保存に失敗しました')).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole('dialog', { name: 'エラー' }).getByRole('button', { name: '閉じる' }).click();
  await expect(killInput).toHaveValue('15');

  await page.unroute('**/api/recorder/metadata');
  await page.waitForTimeout(500);

  await saveButton.click();
  await expect(page.getByText('メタデータを保存しました')).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole('dialog', { name: '完了' }).getByRole('button', { name: '閉じる' }).click();
  await stopRecordingForTeardown(page);
});
```

Create: `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`

```ts
import type { Page } from '@playwright/test';
import { expect, test } from '@playwright/test';

import {
  environment,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAsset,
  recordableReplayAssets,
} from './support/appHelpers';

const e2eEnvironment = environment();
const firstSeedAsset = recordableReplayAssets(e2eEnvironment)[0];
let autoEnableRequestCount = 0;

async function openSeededRecordedVideo(page: Page) {
  if (!firstSeedAsset) {
    test.skip();
    return null;
  }

  prepareRecordedSeedAsset(e2eEnvironment, firstSeedAsset);
  await gotoMain(page);
  await openRecordedVideos(page);
  return firstRecordedVideo(page);
}

test.beforeEach(async ({ page }) => {
  autoEnableRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    autoEnableRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(autoEnableRequestCount).toBe(0);
});

test('エラー復旧 - 録画済みメタデータ更新失敗', async ({ page }) => {
  const recordedVideo = await openSeededRecordedVideo(page);
  if (!recordedVideo) {
    return;
  }

  await recordedVideo.getByTestId('recorded-video-metadata-button').click();
  await page.getByLabel('キル数').fill('50');

  let metadataUpdateRequestCount = 0;
  await page.route('**/api/assets/recorded/*/metadata', (route) => {
    if (route.request().method() === 'PATCH') {
      metadataUpdateRequestCount += 1;
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Failed to update metadata' }),
      });
      return;
    }
    route.continue();
  });

  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();
  await expect.poll(() => metadataUpdateRequestCount, { timeout: 10_000 }).toBe(1);
  await expect(page.getByText(/メタデータの保存に失敗しました:/)).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole('dialog', { name: 'エラー' }).getByRole('button', { name: '閉じる' }).click();

  await page.unroute('**/api/assets/recorded/*/metadata');
  const recordedVideoAfterError = await firstRecordedVideo(page);
  await recordedVideoAfterError.getByTestId('recorded-video-metadata-button').click();
  await page.getByLabel('キル数').fill('50');
  await saveButton.click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });
});

test('エラー復旧 - 録画済みリスト取得失敗', async ({ page }) => {
  if (!firstSeedAsset) {
    test.skip();
    return;
  }

  prepareRecordedSeedAsset(e2eEnvironment, firstSeedAsset);

  let fetchRecordedRequestCount = 0;
  await page.route('**/api/assets/recorded', (route) => {
    fetchRecordedRequestCount += 1;
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Failed to fetch recorded videos' }),
    });
  });

  await page.goto('/');
  await gotoMain(page);
  await expect.poll(() => fetchRecordedRequestCount, { timeout: 10_000 }).toBeGreaterThan(0);

  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(0);
  await expect(page.getByText('録画済みデータはありません')).toBeVisible();

  await page.unroute('**/api/assets/recorded');
  await page.reload();
  await gotoMain(page);
  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(1, {
    timeout: 30_000,
  });
});
```

Continue the same file with these two tests copied from the old spec and only the setup changed to `openSeededRecordedVideo(page)`:

```ts
test('エラー復旧 - 削除確認後の API 失敗', async ({ page }) => {
```

```ts
test('エラー復旧 - バリデーションエラーからの再保存', async ({ page }) => {
```

Create: `frontend/tests/e2e/error-recovery-settings.spec.ts`

```ts
import { expect, test } from '@playwright/test';

import {
  environment,
  gotoMain,
  resetReplayTestState,
} from './support/appHelpers';

const e2eEnvironment = environment();
let autoEnableRequestCount = 0;

test.beforeEach(async ({ page }) => {
  resetReplayTestState(e2eEnvironment);
  autoEnableRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    autoEnableRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(autoEnableRequestCount).toBe(0);
});

test('エラー復旧 - 設定保存失敗時のフィードバック', async ({ page }) => {
  await gotoMain(page);
  await page.getByTestId('settings-button').click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeVisible({
    timeout: 10_000,
  });

  let settingsSaveRequestCount = 0;
  await page.route('**/api/settings', (route) => {
    if (route.request().method() !== 'PUT') {
      route.continue();
      return;
    }
    settingsSaveRequestCount += 1;
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Failed to save settings' }),
    });
  });

  await page.getByTestId('settings-section-behavior').click();
  await page.getByRole('button', { name: '保存' }).click();
  await expect.poll(() => settingsSaveRequestCount, { timeout: 10_000 }).toBe(1);
  await expect(page.getByText('Failed to save settings')).toBeVisible({
    timeout: 10_000,
  });
  await page.unroute('**/api/settings');
  await page.getByRole('button', { name: 'キャンセル' }).click();
});
```

Delete: `frontend/tests/e2e/error-recovery.spec.ts`

Do not carry over the old `ネットワーク切断シミュレーション` block.  
理由: 録画中メタデータ保存失敗と同じ user-visible recovery を E2E で重複検証しており、より広い network abort は失敗要因が広すぎて切り分けを悪化させるため。

- [ ] **Step 3: 分割後の spec 群が通ることを確認する**

Run: `cd frontend && npm run test:e2e -- tests/e2e/error-recovery-recording-live.spec.ts tests/e2e/error-recovery-recorded-assets.spec.ts tests/e2e/error-recovery-settings.spec.ts`

Expected: `7 passed`

- [ ] **Step 4: 旧 spec が残っていないことを確認する**

Run: `rg -n "error-recovery\\.spec\\.ts" frontend/tests/e2e`

Expected: 出力なし

- [ ] **Step 5: コミットする**

```bash
git add frontend/tests/e2e/error-recovery-recording-live.spec.ts frontend/tests/e2e/error-recovery-recorded-assets.spec.ts frontend/tests/e2e/error-recovery-settings.spec.ts
git rm frontend/tests/e2e/error-recovery.spec.ts
git commit -m "test: split error recovery e2e flows"
```

### Task 6: E2E ドキュメントを replay / seed / no-video 分類へ更新する

**Files:**
- Modify: `docs/e2e_replay_test.md`
- Test: `docs/e2e_replay_test.md`

- [ ] **Step 1: 新しい spec 名が未反映であることを確認する**

Run: `rg -n "error-recovery-recording-live|error-recovery-recorded-assets|error-recovery-settings|recorded-metadata-edit-workflow|multi-video-management" docs/e2e_replay_test.md`

Expected: 出力なし

- [ ] **Step 2: replay / seed / no-video の分類と実行入口を追記する**

Replace the outdated suite overview section in `docs/e2e_replay_test.md` with:

~~~md
## 4. 現在の E2E 構成

現在の workflow E2E は「動画ファイルが必要なもの」と「録画済み seed で足りるもの」を分けて運用します。

### 4.1. replay を使う spec

- `tests/e2e/auto-recording-workflow.spec.ts`
  - 自動録画の開始 / 継続 / 停止 / 録画済み一覧反映を replay 経由で検証します。
- `tests/e2e/recording-metadata-edit-workflow.spec.ts`
  - 録画中メタデータ編集を replay 経由で検証します。
- `tests/e2e/error-recovery-recording-live.spec.ts`
  - 録画中 UI を前提にしたエラー復旧だけを replay 経由で検証します。

### 4.2. recorded seed を使う spec

- `tests/e2e/edit-upload-workflow.spec.ts`
- `tests/e2e/multi-video-management.spec.ts`
- `tests/e2e/recorded-metadata-edit-workflow.spec.ts`
- `tests/e2e/error-recovery-recorded-assets.spec.ts`

これらは replay を再生せず、E2E 用 `storage/recorded` に seed した録画済み動画を前提に検証します。  
`/api/recorder/enable-auto` を呼ばないことを spec 側で guard します。

### 4.3. 動画ファイル不要の spec

- `tests/e2e/settings-persistence.spec.ts`
- `tests/e2e/error-recovery-settings.spec.ts`

設定保存や設定エラー復旧は動画状態に依存しないため、recorded seed も replay も使いません。

## 5. 実行入口

### 5.1. suite 全体

```bat
cd /d C:\Users\shogo\repo\splat-replay2
task.exe test:e2e
```

### 5.2. replay を使う spec を個別実行する

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e -- tests/e2e/auto-recording-workflow.spec.ts
npm run test:e2e -- tests/e2e/recording-metadata-edit-workflow.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-recording-live.spec.ts
```

### 5.3. recorded seed の spec を個別実行する

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts
npm run test:e2e -- tests/e2e/multi-video-management.spec.ts
npm run test:e2e -- tests/e2e/recorded-metadata-edit-workflow.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-recorded-assets.spec.ts
```

### 5.4. 動画不要の spec を個別実行する

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e -- tests/e2e/settings-persistence.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-settings.spec.ts
```
~~~

- [ ] **Step 3: ドキュメント更新が入ったことを確認する**

Run: `rg -n "error-recovery-recording-live|error-recovery-recorded-assets|error-recovery-settings|recorded seed|動画ファイル不要" docs/e2e_replay_test.md`

Expected: 5 行以上ヒットする

- [ ] **Step 4: 代表 spec の入口が壊れていないことを確認する**

Run: `cd frontend && npm run test:e2e -- --list`

Expected: `error-recovery-recording-live.spec.ts`, `error-recovery-recorded-assets.spec.ts`, `error-recovery-settings.spec.ts` が一覧に表示される

- [ ] **Step 5: コミットする**

```bash
git add docs/e2e_replay_test.md
git commit -m "docs: update e2e replay test guide"
```
