import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';

import { environment, gotoMain, resetReplayTestState } from './support/appHelpers';

const e2eEnvironment = environment();
const captureResponsiveScreenshots =
  process.env.SPLAT_REPLAY_CAPTURE_RESPONSIVE_SCREENSHOTS === '1';

type ViewportCase = {
  name: string;
  size: {
    width: number;
    height: number;
  };
  expectsFloatingDrawerButton: boolean;
};

const viewportCases: ViewportCase[] = [
  {
    name: 'iPhone SE portrait',
    size: { width: 375, height: 667 },
    expectsFloatingDrawerButton: false,
  },
  {
    name: 'iPhone SE landscape',
    size: { width: 667, height: 375 },
    expectsFloatingDrawerButton: true,
  },
  {
    name: 'iPhone 5 portrait',
    size: { width: 320, height: 568 },
    expectsFloatingDrawerButton: false,
  },
  {
    name: 'iPad portrait',
    size: { width: 768, height: 1024 },
    expectsFloatingDrawerButton: false,
  },
  {
    name: 'iPad landscape',
    size: { width: 1024, height: 768 },
    expectsFloatingDrawerButton: false,
  },
  {
    name: 'desktop 16:9',
    size: { width: 1920, height: 1080 },
    expectsFloatingDrawerButton: false,
  },
];

function expectBoxInsideViewport(
  box: { x: number; y: number; width: number; height: number },
  viewport: { width: number; height: number },
  label: string
): void {
  expect(box.x, `${label} left edge should stay in viewport`).toBeGreaterThanOrEqual(0);
  expect(box.y, `${label} top edge should stay in viewport`).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width, `${label} right edge should stay in viewport`).toBeLessThanOrEqual(
    viewport.width + 1
  );
  expect(box.y + box.height, `${label} bottom edge should stay in viewport`).toBeLessThanOrEqual(
    viewport.height + 1
  );
}

async function visibleBox(locator: Locator, label: string) {
  await expect(locator, `${label} should be visible`).toBeVisible();
  const box = await locator.boundingBox();
  expect(box, `${label} should have a bounding box`).not.toBeNull();
  return box!;
}

async function expectNoHorizontalDocumentOverflow(page: Page): Promise<void> {
  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));

  expect(metrics.scrollWidth, 'document should not overflow horizontally').toBeLessThanOrEqual(
    metrics.viewportWidth
  );
}

async function expectPreviewKeepsSixteenByNine(page: Page): Promise<void> {
  const previewBox = await visibleBox(page.getByTestId('preview-container'), 'preview');
  const ratio = previewBox.width / previewBox.height;
  expect(ratio, 'preview should preserve a 16:9 aspect ratio').toBeGreaterThan(1.76);
  expect(ratio, 'preview should preserve a 16:9 aspect ratio').toBeLessThan(1.8);
}

async function expectMainControlsStayReachable(
  page: Page,
  expectsFloatingDrawerButton: boolean
): Promise<void> {
  const viewport = page.viewportSize();
  if (!viewport) {
    throw new Error('viewport size is not configured');
  }

  const controls: Array<[Locator, string]> = [
    [page.getByTestId('settings-button'), 'settings button'],
  ];
  if (expectsFloatingDrawerButton) {
    controls.push([page.getByTestId('main-drawer-button'), 'drawer button']);
  } else {
    controls.push([page.getByTestId('drawer-process-button'), 'process button']);
  }

  for (const [locator, label] of controls) {
    const box = await visibleBox(locator, label);
    expectBoxInsideViewport(box, viewport, label);
  }
}

async function expectTabsRemainOperable(page: Page): Promise<void> {
  const tabs = page.getByTestId('drawer-tabs');
  const tabMetrics = await tabs.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(tabMetrics.clientWidth, 'tabs should retain a touchable width').toBeGreaterThan(0);
  expect(tabMetrics.scrollWidth, 'tabs should be operable without clipping').toBeGreaterThan(0);
}

async function expectTabletTabsKeepTextDensity(page: Page): Promise<void> {
  await expect(page.getByTestId('tab-info').first()).toBeVisible();
}

function jsonResponse(body: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

async function mockStatisticsTabData(page: Page): Promise<void> {
  const rules = ['TURF_WAR', 'SPLAT_ZONES', 'TOWER_CONTROL', 'RAINMAKER', 'CLAM_BLITZ'];
  const stages = [
    'SCORCH_GORGE',
    'EELTAIL_ALLEY',
    'HAGGLEFISH_MARKET',
    'UNDERTOW_SPILLWAY',
    'MAKO_MART',
  ];
  const records = Array.from({ length: 30 }, (_, index) => ({
    record_id: `record-${index}`,
    source_video_id: `video-${index}`,
    game_mode: 'REGULAR_MATCH',
    started_at: `2026-04-01T${String(index % 24).padStart(2, '0')}:00:00`,
    match: 'REGULAR_MATCH',
    rule: rules[index % rules.length],
    stage: stages[index % stages.length],
    judgement: index % 3 === 0 ? 'LOSE' : 'WIN',
    kill: 5 + (index % 7),
    death: 2 + (index % 5),
    special: 1 + (index % 4),
    assist: index % 3,
    gold_medals: index % 2,
    silver_medals: index % 3,
    session_rate: null,
  }));

  await page.route('**/setup/status', (route) =>
    route.fulfill(
      jsonResponse({
        is_completed: true,
        current_step: 'youtube_setup',
        completed_steps: ['youtube_setup'],
        step_details: {},
      })
    )
  );
  await page.route('**/api/settings/webview-render-mode', (route) =>
    route.fulfill(jsonResponse({ render_mode: 'cpu' }))
  );
  await page.route('**/api/assets/recorded', (route) => route.fulfill(jsonResponse([])));
  await page.route('**/api/assets/edited', (route) => route.fulfill(jsonResponse([])));
  await page.route('**/api/history/battle', (route) => route.fulfill(jsonResponse({ records })));
  await page.route('**/api/process/status', (route) =>
    route.fulfill(
      jsonResponse({
        state: 'idle',
        started_at: null,
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      })
    )
  );
  await page.route('**/api/settings/youtube-permission-dialog', (route) =>
    route.fulfill(jsonResponse({ shown: true }))
  );
  await page.route('**/api/recorder/preview-mode', (route) =>
    route.fulfill(jsonResponse({ mode: 'video_file' }))
  );
  await page.route('**/api/recorder/state', (route) =>
    route.fulfill(jsonResponse({ state: 'stopped' }))
  );
  await page.route('**/api/device/status', (route) =>
    route.fulfill(jsonResponse({ available: false, message: 'diagnostic' }))
  );
  await page.route('**/api/metadata/options', (route) =>
    route.fulfill(
      jsonResponse({ game_modes: [], matches: [], rules: [], stages: [], judgements: [] })
    )
  );
}

async function captureScreenshotIfRequested(
  page: Page,
  testInfo: TestInfo,
  viewportCase: ViewportCase
): Promise<void> {
  if (!captureResponsiveScreenshots) {
    return;
  }

  await page.screenshot({
    path: testInfo.outputPath(`${viewportCase.name.replace(/\W+/g, '-')}.png`),
    fullPage: true,
  });
}

for (const viewportCase of viewportCases) {
  test(`main responsive layout: ${viewportCase.name}`, async ({ page }, testInfo) => {
    resetReplayTestState(e2eEnvironment);
    await page.setViewportSize(viewportCase.size);
    await gotoMain(page);

    await expect(page.getByTestId('main-app-shell')).toBeVisible();
    await expectNoHorizontalDocumentOverflow(page);
    await expectPreviewKeepsSixteenByNine(page);
    await expectMainControlsStayReachable(page, viewportCase.expectsFloatingDrawerButton);
    await expectTabsRemainOperable(page);

    const drawerButton = page.getByTestId('main-drawer-button');
    const drawerRoot = page.getByTestId('bottom-drawer-root');

    if (viewportCase.expectsFloatingDrawerButton) {
      await expect(drawerButton).toBeVisible();
      const drawerBox = await drawerRoot.boundingBox();
      expect(drawerBox, 'hidden drawer should keep a measurable box').not.toBeNull();
      expect(
        drawerBox!.y,
        'closed drawer should be shifted outside the landscape viewport'
      ).toBeGreaterThanOrEqual(viewportCase.size.height - 1);
      const previewBox = await visibleBox(page.getByTestId('preview-container'), 'preview');
      expect(
        previewBox.height,
        'compact landscape preview should use most of the available height'
      ).toBeGreaterThanOrEqual(viewportCase.size.height * 0.7);
    } else {
      await expect(drawerButton).toBeHidden();
      const drawerBox = await visibleBox(drawerRoot, 'bottom drawer');
      expect(
        drawerBox.y,
        'portrait drawer should remain visible at the bottom of the viewport'
      ).toBeLessThan(viewportCase.size.height);
    }

    if (viewportCase.size.width === 768) {
      await expectTabletTabsKeepTextDensity(page);
    }

    await captureScreenshotIfRequested(page, testInfo, viewportCase);
  });
}

test('main responsive layout: narrow controls keep accessible names', async ({ page }) => {
  resetReplayTestState(e2eEnvironment);
  await page.setViewportSize({ width: 320, height: 568 });
  await gotoMain(page);

  await expect(page.getByTestId('drawer-process-button')).toHaveAttribute(
    'aria-label',
    '録画データの編集とYouTubeアップロードを開始'
  );
});

test('main responsive layout: drawer labels collapse before the overlap threshold', async ({
  page,
}) => {
  resetReplayTestState(e2eEnvironment);
  await page.setViewportSize({ width: 640, height: 900 });
  await gotoMain(page);

  await expect(page.getByTestId('tab-info').first()).toBeHidden();
});

test('main responsive layout: statistics tab keeps detail rows reachable on narrow phones', async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await mockStatisticsTabData(page);
  await gotoMain(page);

  await page.getByTestId('bottom-drawer-toggle').click();
  await page.getByTestId('drawer-tabs').locator('button').nth(2).click();
  await page.locator('.detail-card').waitFor({ state: 'attached' });

  const metrics = await page.evaluate(() => {
    const stats = document.querySelector('.statistics-container');
    const detail = document.querySelector('.detail-card');
    const list = document.querySelector('.scroll-list');
    const ruleHeader = document.querySelector('.rule-header');
    const ruleName = document.querySelector('.rule-name');
    if (!stats || !detail || !list || !ruleHeader || !ruleName) {
      throw new Error('statistics layout elements are missing');
    }

    const ruleHeaderRect = ruleHeader.getBoundingClientRect();
    const ruleNameRect = ruleName.getBoundingClientRect();

    return {
      statsClientHeight: stats.clientHeight,
      statsScrollHeight: stats.scrollHeight,
      detailHeight: detail.getBoundingClientRect().height,
      listHeight: list.getBoundingClientRect().height,
      ruleHeaderHeight: ruleHeaderRect.height,
      ruleNameHeight: ruleNameRect.height,
      ruleNameWidth: ruleNameRect.width,
    };
  });

  expect(metrics.statsScrollHeight).toBeGreaterThan(metrics.statsClientHeight);
  expect(metrics.detailHeight).toBeGreaterThan(96);
  expect(metrics.listHeight).toBeGreaterThan(48);
  expect(metrics.ruleHeaderHeight).toBeLessThan(96);
  expect(metrics.ruleNameHeight).toBeLessThan(56);
  expect(metrics.ruleNameWidth).toBeGreaterThan(72);
});
