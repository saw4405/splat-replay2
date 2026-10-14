import { expect, test } from '@playwright/test';

test('必須設定不足がある完了済み環境をセットアップへ戻し、対象カードを開く', async ({ page }) => {
  const issue = {
    code: 'youtube_client_secret_invalid',
    step: 'youtube_setup',
    substep_id: 'youtube-place-file',
    message: '有効な YouTube OAuth client_secret.json を配置してください。',
  };

  // 具体stubより先に登録し、想定外のAPI呼び出しでbackendへ接続しないようにする。
  await page.route(
    (url) => url.pathname.startsWith('/api/'),
    (route) => route.abort()
  );
  await page.route(
    (url) => url.pathname.startsWith('/setup/'),
    (route) => route.abort()
  );

  await page.route('**/api/settings/webview-render-mode', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ render_mode: 'gpu' }),
    })
  );
  await page.route('**/setup/status**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        is_completed: true,
        current_step: 'youtube_setup',
        completed_steps: [],
        skipped_steps: [],
        step_details: {},
        required_setup_issues: [issue],
        installation_date: null,
        server_platform: 'windows',
      }),
    })
  );
  await page.route('**/setup/system/check/youtube', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_installed: false }),
    })
  );
  await page.route('**/setup/repair/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(issue),
    })
  );

  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: '起動に必要な設定が不足しています' })
  ).toBeVisible();
  await expect(page.getByRole('button', { name: '処理開始' })).toHaveCount(0);
  await page.getByRole('button', { name: '修復する' }).click();

  await expect(page.getByRole('heading', { name: '認証情報ファイルの配置' })).toBeVisible();
});
