import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';
import type { ProgressEvent } from '../../src/main/api/types';

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

type ProgressDialogViewportCase = {
  name: string;
  size: {
    width: number;
    height: number;
  };
  expectsCompactStages: boolean;
  expectsFullscreen: boolean;
};

const progressDialogViewportCases: ProgressDialogViewportCase[] = [
  {
    name: '900px boundary',
    size: { width: 900, height: 720 },
    expectsCompactStages: true,
    expectsFullscreen: false,
  },
  {
    name: '901px desktop',
    size: { width: 901, height: 720 },
    expectsCompactStages: false,
    expectsFullscreen: false,
  },
  {
    name: '320px phone',
    size: { width: 320, height: 568 },
    expectsCompactStages: true,
    expectsFullscreen: true,
  },
];

async function mockRunningProcessStatus(page: Page): Promise<void> {
  await page.route('**/api/process/status', (route) =>
    route.fulfill(
      jsonResponse({
        state: 'running',
        started_at: '2026-07-11T00:00:00Z',
        finished_at: null,
        error: null,
        sleep_after_upload_default: false,
        sleep_after_upload_effective: false,
        sleep_after_upload_overridden: false,
      })
    )
  );
}

type ProgressEventControllerWindow = Window & {
  __emitProgressEvent?: (event: ProgressEvent) => number;
};

async function installControllableProgressEventSource(page: Page): Promise<void> {
  await page.addInitScript(() => {
    class MockEventSource extends EventTarget {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSED = 2;
      static readonly sources = new Set<MockEventSource>();

      readonly CONNECTING = MockEventSource.CONNECTING;
      readonly OPEN = MockEventSource.OPEN;
      readonly CLOSED = MockEventSource.CLOSED;
      readonly url: string;
      readonly withCredentials: boolean;
      readyState = MockEventSource.CONNECTING;
      onerror: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onopen: ((event: Event) => void) | null = null;

      constructor(url: string | URL, eventSourceInitDict?: EventSourceInit) {
        super();
        this.url = String(url);
        this.withCredentials = eventSourceInitDict?.withCredentials ?? false;
        MockEventSource.sources.add(this);

        queueMicrotask(() => {
          if (this.readyState === MockEventSource.CLOSED) {
            return;
          }

          this.readyState = MockEventSource.OPEN;
          const openEvent = new Event('open');
          this.dispatchEvent(openEvent);
          this.onopen?.(openEvent);
        });
      }

      close(): void {
        this.readyState = MockEventSource.CLOSED;
        MockEventSource.sources.delete(this);
      }
    }

    Object.defineProperty(window, 'EventSource', {
      configurable: true,
      writable: true,
      value: MockEventSource,
    });

    const controllerWindow = window as ProgressEventControllerWindow;
    controllerWindow.__emitProgressEvent = (payload: ProgressEvent): number => {
      let receiverCount = 0;

      for (const source of MockEventSource.sources) {
        if (
          !source.url.endsWith('/api/events/progress') ||
          source.readyState === MockEventSource.CLOSED
        ) {
          continue;
        }

        source.dispatchEvent(
          new MessageEvent('progress_event', {
            data: JSON.stringify(payload),
          })
        );
        receiverCount++;
      }

      return receiverCount;
    };
  });
}

async function emitProgressEvent(page: Page, event: ProgressEvent): Promise<void> {
  const receiverCount = await page.evaluate((payload) => {
    const controllerWindow = window as ProgressEventControllerWindow;
    if (!controllerWindow.__emitProgressEvent) {
      throw new Error('progress EventSource controller is not installed');
    }
    return controllerWindow.__emitProgressEvent(payload);
  }, event);

  expect(receiverCount, 'progress event should reach an active EventSource').toBeGreaterThan(0);
}

for (const viewportCase of progressDialogViewportCases) {
  test(`progress dialog responsive: ${viewportCase.name}`, async ({ page }) => {
    resetReplayTestState(e2eEnvironment);
    await page.setViewportSize(viewportCase.size);
    await installControllableProgressEventSource(page);
    await mockRunningProcessStatus(page);
    await gotoMain(page);

    const dialog = page.getByRole('dialog', { name: '進捗' });
    const editing = dialog.getByRole('region', { name: '1. 編集', exact: true });
    const waiting = dialog.getByRole('region', { name: '2. 待機', exact: true });
    const uploading = dialog.getByRole('region', { name: '3. アップロード', exact: true });
    const waitingDetail = waiting.getByText('編集完了した動画がここに蓄積されます', {
      exact: true,
    });

    await expect(dialog).toBeVisible();

    if (viewportCase.name === '900px boundary') {
      await emitProgressEvent(page, {
        task_id: 'auto_edit',
        kind: 'start',
        task_name: '自動編集',
        total: 2,
        completed: 0,
        stage_key: null,
        stage_label: null,
        stage_index: null,
        stage_count: null,
        success: null,
        message: null,
        items: ['処理中動画', '後続動画'],
        item_index: null,
        item_key: null,
        item_label: null,
        progress_percent: null,
        clips: [
          {
            group_index: 0,
            date_label: '07/14 12:00～',
            match_name: 'Xマッチ',
            rule_name: 'ガチヤグラ',
            video_assets: [
              {
                video_id: 'recorded/current.mkv',
                duration_seconds: 300,
                judgement: 'WIN',
                stage_name: 'FLOUNDER_HEIGHTS',
                kill: 9,
                death: 7,
                special: 5,
                gold_medals: 2,
                silver_medals: 1,
                rate: null,
              },
            ],
          },
          {
            group_index: 1,
            date_label: '07/14 12:10～',
            match_name: 'Xマッチ',
            rule_name: 'ガチヤグラ',
            video_assets: [
              {
                video_id: 'recorded/queued.mkv',
                duration_seconds: 300,
                judgement: 'LOSE',
                stage_name: 'FLOUNDER_HEIGHTS',
                kill: 5,
                death: 8,
                special: 3,
                gold_medals: 1,
                silver_medals: 1,
                rate: null,
              },
            ],
          },
        ],
      });
      await emitProgressEvent(page, {
        task_id: 'auto_edit',
        kind: 'item_stage',
        task_name: '自動編集',
        total: 2,
        completed: 0,
        stage_key: null,
        stage_label: null,
        stage_index: null,
        stage_count: null,
        success: null,
        message: '動画結合中',
        items: null,
        item_index: 0,
        item_key: 'concat',
        item_label: '動画結合',
        progress_percent: 40,
        clips: null,
      });
    }

    await expect(dialog).toHaveCSS('transform', 'none');
    await expect(editing).toHaveAttribute('aria-current', 'step');
    await expect(waiting).not.toHaveAttribute('aria-current', 'step');
    await expect(uploading).not.toHaveAttribute('aria-current', 'step');
    await expect(
      dialog.getByRole('region', {
        name: 'YouTubeアップロードエリア 待機中',
        exact: true,
      })
    ).toBeAttached();

    const overflow = await dialog.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(
      overflow.scrollWidth,
      'progress dialog should not overflow horizontally'
    ).toBeLessThanOrEqual(overflow.clientWidth);

    const editingBox = await visibleBox(editing, 'editing stage');
    const waitingBox = await visibleBox(waiting, 'waiting stage');
    const uploadingBox = await visibleBox(uploading, 'uploading stage');

    if (viewportCase.expectsCompactStages) {
      await expect(waitingDetail).toBeHidden();

      expect(waitingBox.y).toBeGreaterThan(editingBox.y);
      expect(uploadingBox.y).toBeGreaterThan(waitingBox.y);
      expect(Math.abs(waitingBox.width - editingBox.width)).toBeLessThanOrEqual(1);
      expect(Math.abs(uploadingBox.width - editingBox.width)).toBeLessThanOrEqual(1);
      expect(waitingBox.height).toBeLessThanOrEqual(45);
      expect(uploadingBox.height).toBeLessThanOrEqual(45);
      expect(editingBox.height).toBeGreaterThan(waitingBox.height * 3);

      if (viewportCase.name === '900px boundary') {
        const progressBody = dialog.getByTestId('progress-scroll-body');
        const previewFrame = dialog.getByAltText('Preview Frame').first();
        const currentTimeline = dialog.getByText('07/14 12:00～', { exact: true }).locator('..');
        const queuedTimeline = dialog.getByText('07/14 12:10～', { exact: true });

        await expect(queuedTimeline).toBeHidden();

        const progressBodyBox = await visibleBox(progressBody, 'progress body');
        const previewFrameBox = await visibleBox(previewFrame, 'current preview frame');
        const currentTimelineBox = await visibleBox(currentTimeline, 'current timeline');
        const scrollTop = await progressBody.evaluate((element) => element.scrollTop);

        expect(scrollTop, 'progress body should stay at its initial position').toBe(0);
        expect(
          previewFrameBox.y,
          'preview should start inside the visible progress body'
        ).toBeGreaterThanOrEqual(progressBodyBox.y);
        expect(
          currentTimelineBox.y + currentTimelineBox.height,
          'current timeline should fit below the preview without scrolling'
        ).toBeLessThanOrEqual(progressBodyBox.y + progressBodyBox.height + 1);

        const previewRatio = previewFrameBox.width / previewFrameBox.height;
        expect(previewRatio, 'progress preview should preserve 16:9').toBeGreaterThan(1.76);
        expect(previewRatio, 'progress preview should preserve 16:9').toBeLessThan(1.8);
      }
    } else {
      await expect(waitingDetail).toBeVisible();

      expect(waitingBox.x).toBeGreaterThan(editingBox.x);
      expect(uploadingBox.x).toBeGreaterThan(waitingBox.x);
      expect(Math.abs(waitingBox.y - editingBox.y)).toBeLessThanOrEqual(1);
      expect(Math.abs(uploadingBox.y - editingBox.y)).toBeLessThanOrEqual(1);
    }

    if (viewportCase.expectsFullscreen) {
      const dialogBox = await visibleBox(dialog, 'fullscreen progress dialog');
      expectBoxInsideViewport(dialogBox, viewportCase.size, 'fullscreen progress dialog');
      expect(dialogBox.x, 'fullscreen dialog left inset').toBeLessThanOrEqual(1);
      expect(dialogBox.y, 'fullscreen dialog top inset').toBeLessThanOrEqual(1);
      expect(
        viewportCase.size.width - (dialogBox.x + dialogBox.width),
        'fullscreen dialog right inset'
      ).toBeLessThanOrEqual(1);
      expect(
        viewportCase.size.height - (dialogBox.y + dialogBox.height),
        'fullscreen dialog bottom inset'
      ).toBeLessThanOrEqual(1);

      const progressBody = dialog.getByTestId('progress-scroll-body');
      const bodyOverflow = await progressBody.evaluate((element) => ({
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        scrollTop: element.scrollTop,
      }));
      expect(
        bodyOverflow.scrollHeight,
        'phone progress body should have its own vertical scroll range'
      ).toBeGreaterThan(bodyOverflow.clientHeight);

      await uploading.evaluate((element) => {
        element.scrollIntoView({ behavior: 'auto', block: 'end' });
      });
      await expect
        .poll(() => progressBody.evaluate((element) => element.scrollTop), {
          message: 'progress body should scroll toward the last stage',
        })
        .toBeGreaterThan(bodyOverflow.scrollTop);

      const progressBodyBox = await visibleBox(progressBody, 'scrollable progress body');
      const reachedUploadingBox = await visibleBox(uploading, 'reached uploading stage');
      expect(
        reachedUploadingBox.y + reachedUploadingBox.height,
        'last stage bottom should be reachable inside the progress body'
      ).toBeLessThanOrEqual(progressBodyBox.y + progressBodyBox.height + 1);

      const closeButton = dialog.getByRole('button', { name: '閉じる', exact: true }).last();
      const closeButtonBox = await visibleBox(closeButton, 'progress close button');
      expectBoxInsideViewport(closeButtonBox, viewportCase.size, 'progress close button');
      expect(closeButtonBox.height).toBeGreaterThanOrEqual(44);

      const sleepToggle = dialog.getByRole('checkbox', {
        name: '完了後スリープ',
        exact: true,
      });
      await expect(sleepToggle).toBeAttached();
      const sleepToggleBox = await sleepToggle.evaluate((checkbox) => {
        const label = (checkbox as HTMLInputElement).labels?.[0];
        if (!label) {
          throw new Error('sleep-after-upload checkbox label is missing');
        }

        const rect = label.getBoundingClientRect();
        return {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        };
      });
      expectBoxInsideViewport(sleepToggleBox, viewportCase.size, 'sleep-after-upload toggle');
      expect(sleepToggleBox.height).toBeGreaterThanOrEqual(44);
    }

    await emitProgressEvent(page, {
      task_id: 'auto_upload',
      kind: 'start',
      task_name: '自動アップロード',
      total: 1,
      completed: 0,
      stage_key: null,
      stage_label: null,
      stage_index: null,
      stage_count: null,
      success: null,
      message: null,
      items: null,
      item_index: null,
      item_key: null,
      item_label: null,
      progress_percent: null,
      clips: null,
    });

    await expect(uploading).toHaveAttribute('aria-current', 'step');
    await expect(editing).not.toHaveAttribute('aria-current', 'step');
    await expect(waiting).not.toHaveAttribute('aria-current', 'step');
    await expect(
      dialog.getByRole('region', {
        name: 'YouTubeアップロードエリア 展開中',
        exact: true,
      })
    ).toBeVisible();
    await expect(uploading.getByRole('progressbar', { name: 'YouTube再構成進捗' })).toBeVisible();

    if (viewportCase.expectsCompactStages) {
      const collapsedEditingBox = await visibleBox(editing, 'collapsed editing stage');
      const collapsedWaitingBox = await visibleBox(waiting, 'collapsed waiting stage');
      const activeUploadingBox = await visibleBox(uploading, 'active uploading stage');

      expect(collapsedEditingBox.height).toBeLessThanOrEqual(45);
      expect(collapsedWaitingBox.height).toBeLessThanOrEqual(45);
      expect(activeUploadingBox.height).toBeGreaterThan(collapsedEditingBox.height * 3);
      expect(Math.abs(collapsedWaitingBox.width - activeUploadingBox.width)).toBeLessThanOrEqual(1);
      expect(Math.abs(collapsedEditingBox.width - activeUploadingBox.width)).toBeLessThanOrEqual(1);
    }
  });
}
