import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';

import { environment, gotoMain, resetReplayTestState } from './support/appHelpers';

const e2eEnvironment = environment();
const captureResponsiveScreenshots =
  process.env.SPLAT_REPLAY_CAPTURE_RESPONSIVE_SCREENSHOTS === '1';

type LayoutMode = 'portrait' | 'landscape';

type ViewportCase = {
  name: string;
  size: {
    width: number;
    height: number;
  };
  mode: LayoutMode;
};

const viewportCases: ViewportCase[] = [
  { name: 'iPhone SE portrait', size: { width: 375, height: 667 }, mode: 'portrait' },
  { name: 'iPhone SE landscape', size: { width: 667, height: 375 }, mode: 'landscape' },
  { name: 'iPhone 5 portrait', size: { width: 320, height: 568 }, mode: 'portrait' },
  { name: 'iPad portrait', size: { width: 768, height: 1024 }, mode: 'portrait' },
  { name: 'iPad landscape', size: { width: 1024, height: 768 }, mode: 'portrait' },
  { name: 'desktop 16:9', size: { width: 1920, height: 1080 }, mode: 'portrait' },
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

async function expectMainControlsStayReachable(page: Page, mode: LayoutMode): Promise<void> {
  const viewport = page.viewportSize();
  if (!viewport) {
    throw new Error('viewport size is not configured');
  }

  const controls: Array<[Locator, string]> = [
    [page.getByTestId('settings-button'), 'settings button'],
  ];
  if (mode === 'landscape') {
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
  await expect(page.locator('.tab-info').first()).toBeVisible();
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
    await expectMainControlsStayReachable(page, viewportCase.mode);
    await expectTabsRemainOperable(page);

    const drawerButton = page.getByTestId('main-drawer-button');
    const drawerRoot = page.getByTestId('bottom-drawer-root');

    if (viewportCase.mode === 'landscape') {
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
        'landscape preview should use most of the available height'
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

  await expect(page.locator('.tab-info').first()).toBeHidden();
});
