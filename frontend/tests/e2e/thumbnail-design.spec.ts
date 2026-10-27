import { expect, test } from '@playwright/test';
import { environment, gotoMain, resetReplayTestState } from './support/appHelpers';

test('thumbnail-design: 編集から生成確認・保存・取消まで', async ({ page }) => {
  resetReplayTestState(environment());
  await gotoMain(page);
  async function openEditor(): Promise<void> {
    await page.getByTestId('settings-button').click();
    await page.getByRole('radio', { name: 'すべての設定' }).click();
    await page.getByRole('tab', { name: '編集', exact: true }).click();
    await page.getByRole('button', { name: 'サムネイルデザインを編集' }).click();
    await expect(page.getByRole('dialog', { name: 'サムネイルデザイン' })).toBeVisible();
  }
  await openEditor();
  const editor = page.getByRole('dialog', { name: 'サムネイルデザイン' });
  await expect(
    editor.getByRole('img', { name: 'サンプルデータによるサムネイルのプレビュー' })
  ).toBeVisible();
  await expect(editor.getByLabel('テンプレート', { exact: true })).toHaveValue('{WIN} - {LOSE}');
  await expect(editor.getByLabel('X', { exact: true })).toHaveValue('458');
  await expect(editor.getByLabel('Y', { exact: true })).toHaveValue('100');
  await expect(editor.getByRole('combobox', { name: '背景', exact: true })).toBeVisible();
  await expect(editor.getByText('サンプルで編集中', { exact: true })).toHaveCount(0);
  await expect(editor.getByRole('button', { name: '適用', exact: true })).toBeEnabled();
  const preview = editor.getByRole('img', { name: 'サンプルデータによるサムネイルのプレビュー' });
  await expect
    .poll(async () => {
      const image = await preview.boundingBox();
      const workspace = await editor
        .getByRole('region', { name: 'サムネイルプレビュー' })
        .boundingBox();
      return (
        !!image &&
        !!workspace &&
        image.height > 100 &&
        image.y >= workspace.y &&
        image.y + image.height < workspace.y + workspace.height - 25
      );
    })
    .toBe(true);
  await page.screenshot({ path: '../.tmp/thumbnail-redesign/initial.png', fullPage: true });
  const catalog = await (await page.request.get('/api/thumbnail-design')).json();
  const backgroundAsset = catalog.assets.find((asset: { kind: string }) => asset.kind === 'image');
  const originalImage = await preview.getAttribute('src');
  await editor.getByRole('combobox', { name: '背景', exact: true }).selectOption('image');
  await editor
    .getByRole('combobox', { name: '背景画像', exact: true })
    .selectOption(backgroundAsset.id);
  await expect(preview).not.toHaveAttribute('src', originalImage!);
  await editor.getByRole('combobox', { name: '背景', exact: true }).selectOption('result');
  await expect(preview).toHaveAttribute('src', originalImage!);
  await editor.getByLabel('テンプレート', { exact: true }).fill('{WIN} / {LOSE}');
  const handle = editor.getByRole('button', { name: '勝敗の位置を調整' });
  const rect = await handle.boundingBox();
  expect(rect).not.toBeNull();
  if (!rect) throw new Error('勝敗要素の移動範囲がありません');
  const previousX = await editor.getByLabel('X', { exact: true }).inputValue();
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
  await page.mouse.down();
  await page.mouse.move(rect.x + rect.width / 2 + 30, rect.y + rect.height / 2 + 15, { steps: 5 });
  await page.mouse.up();
  await expect(editor.getByLabel('X', { exact: true })).not.toHaveValue(previousX);
  await editor.getByRole('button', { name: '図形を追加' }).click();
  await expect(editor.getByRole('combobox', { name: '図形', exact: true })).toBeVisible();
  await editor.getByRole('button', { name: '元に戻す', exact: true }).click();
  await expect(editor.getByRole('combobox', { name: '図形', exact: true })).toBeHidden();
  await editor.getByRole('button', { name: 'やり直す', exact: true }).click();
  await expect(editor.getByRole('combobox', { name: '図形', exact: true })).toBeVisible();
  await editor.getByRole('combobox', { name: '図形', exact: true }).selectOption('ellipse');
  await editor.getByRole('button', { name: 'スポイト', exact: true }).click();
  await editor
    .getByRole('button', { name: 'プレビューから色を取得' })
    .click({ position: { x: 10, y: 10 } });
  await expect(editor.getByRole('button', { name: 'プレビューから色を取得' })).toBeHidden();
  await editor.getByRole('button', { name: '要素を削除' }).click();
  await expect(editor.getByRole('button', { name: '適用', exact: true })).toBeEnabled();
  await editor.getByRole('button', { name: '適用', exact: true }).click();
  await expect(
    editor.getByRole('img', { name: '実際の生成処理によるサンプルサムネイル' })
  ).toBeVisible();
  await editor.getByRole('button', { name: '編集に戻る' }).click();
  await page.screenshot({ path: '../.tmp/thumbnail-redesign/edited.png', fullPage: true });
  await expect(editor.getByRole('button', { name: '適用', exact: true })).toBeEnabled();
  await editor.getByRole('button', { name: '適用', exact: true }).click();
  await editor.getByRole('button', { name: 'このデザインを使う' }).click();
  await page
    .getByRole('dialog', { name: '設定', exact: true })
    .getByRole('button', { name: '保存', exact: true })
    .click();
  await openEditor();
  await expect(editor.getByLabel('テンプレート', { exact: true })).toHaveValue('{WIN} / {LOSE}');
  await editor.getByLabel('テンプレート', { exact: true }).fill('discard');
  await expect(editor.getByRole('button', { name: '適用', exact: true })).toBeEnabled();
  await editor.getByRole('button', { name: '適用', exact: true }).click();
  await editor.getByRole('button', { name: 'このデザインを使う' }).click();
  await page
    .getByRole('dialog', { name: '設定', exact: true })
    .getByRole('button', { name: 'キャンセル', exact: true })
    .click();
  await openEditor();
  await expect(editor.getByLabel('テンプレート', { exact: true })).toHaveValue('{WIN} / {LOSE}');
});

test('thumbnail-design: 四領域で背景と文字を直接編集する', async ({ page }) => {
  resetReplayTestState(environment());
  await page.setViewportSize({ width: 1042, height: 864 });
  await gotoMain(page);
  await page.getByTestId('settings-button').click();
  await page.getByRole('radio', { name: 'すべての設定' }).click();
  await page.getByRole('tab', { name: '編集', exact: true }).click();
  await page.getByRole('button', { name: 'サムネイルデザインを編集' }).click();
  const editor = page.getByRole('dialog', { name: 'サムネイルデザイン' });
  const background = editor.getByRole('region', { name: '背景の設定' });
  const properties = editor.getByRole('region', { name: '選択した要素の編集' });
  const elements = editor.getByRole('region', { name: '要素の管理' });
  await expect(
    editor.getByRole('img', { name: 'サンプルデータによるサムネイルのプレビュー' })
  ).toBeVisible();
  await expect
    .poll(async () => {
      const rect = await properties
        .getByRole('textbox', { name: 'テンプレート', exact: true })
        .boundingBox();
      const parent = await properties.boundingBox();
      return (
        !!rect && !!parent && rect.y >= parent.y && rect.y + rect.height <= parent.y + parent.height
      );
    })
    .toBe(true);
  await page.screenshot({ path: '../.tmp/thumbnail-redesign/layout-1042.png', fullPage: true });
  await background.getByRole('button', { name: '背景をドラッグで移動' }).click();
  const handle = editor.getByRole('button', { name: '背景の位置を調整' });
  const rect = await handle.boundingBox();
  if (!rect) throw new Error('背景の操作範囲がありません');
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
  await page.mouse.down();
  await page.mouse.move(rect.x + rect.width / 2 + 25, rect.y + rect.height / 2 + 15, { steps: 5 });
  await page.mouse.up();
  await expect(background.getByRole('spinbutton', { name: '背景のX' })).not.toHaveValue('0');
  const backgroundPreview = editor.getByRole('img', {
    name: 'サンプルデータによるサムネイルのプレビュー',
  });
  const beforeScale = await backgroundPreview.getAttribute('src');
  await background.getByRole('slider', { name: '背景の倍率' }).press('End');
  await expect(background.getByRole('slider', { name: '背景の倍率' })).toHaveValue('4');
  await expect(backgroundPreview).not.toHaveAttribute('src', beforeScale!);
  await page.keyboard.press('Escape');
  await expect(handle).toBeHidden();
  await background.getByRole('button', { name: '背景の位置・倍率を戻す' }).click();
  await expect(background.getByRole('slider', { name: '背景の倍率' })).toHaveValue('1');
  await expect(background.getByRole('spinbutton', { name: '背景のX' })).toHaveValue('0');
  await elements.getByRole('button', { name: '文字を追加' }).click();
  const content = properties.getByRole('textbox', { name: '文字内容' });
  await expect(content).toBeFocused();
  await content.fill('BEST PLAY');
  await expect(editor.getByRole('button', { name: '文字の位置を調整', exact: true })).toBeVisible();
  await elements.getByRole('checkbox', { name: '文字を表示', exact: true }).uncheck();
  await expect(editor.getByRole('button', { name: '文字の位置を調整', exact: true })).toBeHidden();
  await elements.getByRole('checkbox', { name: '文字を表示', exact: true }).check();
  await editor.getByRole('button', { name: '文字の位置を調整', exact: true }).dblclick();
  await expect(content).toBeFocused();
  const beforeBackground = await backgroundPreview.getAttribute('src');
  await background.getByRole('combobox', { name: '背景', exact: true }).selectOption('image');
  await background
    .getByRole('combobox', { name: '背景画像', exact: true })
    .selectOption('ヒラメが丘団地.png');
  await expect(backgroundPreview).not.toHaveAttribute('src', beforeBackground!);
  await expect(editor.getByRole('button', { name: '適用', exact: true })).toBeEnabled();
  await page.screenshot({
    path: '../.tmp/thumbnail-redesign/contrast-background.png',
    fullPage: true,
  });
  // 明るい背景でも選択枠を確認するための、白い2×2pxのPNG。
  const uploadedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/thumbnail-design/assets') &&
      response.request().method() === 'POST'
  );
  const beforeWhite = await backgroundPreview.getAttribute('src');
  await background.getByLabel('背景画像をアップロード').setInputFiles({
    name: 'contrast-white.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg==',
      'base64'
    ),
  });
  const uploaded = (await (await uploadedResponse).json()) as { id: string };
  await expect(backgroundPreview).not.toHaveAttribute('src', beforeWhite!);
  await page.keyboard.press('Escape');
  await expect(editor.getByRole('button', { name: '背景の位置を調整' })).toBeHidden();
  await page.screenshot({ path: '../.tmp/thumbnail-redesign/contrast-white.png', fullPage: true });
  await elements.getByRole('button', { name: '要素を削除' }).click();
  await expect(properties.getByRole('textbox', { name: '文字内容' })).toBeHidden();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(background.getByRole('slider', { name: '背景の倍率' })).toBeVisible();
  await elements.getByRole('button', { name: '文字を追加' }).click();
  await expect(properties.getByRole('textbox', { name: '文字内容' })).toBeFocused();
  await page.screenshot({ path: '../.tmp/thumbnail-redesign/layout-mobile.png', fullPage: true });
  await editor.getByRole('button', { name: 'キャンセル', exact: true }).click();
  const catalog = await (await page.request.get('/api/thumbnail-design')).json();
  const deletion = await page.request.post('/api/thumbnail-design/assets/delete', {
    data: { asset_id: uploaded.id, draft: catalog.default_design },
  });
  expect(deletion.ok()).toBe(true);
});

test('thumbnail-design: 空白で選択解除し、入力欄のヒントから変数をコピーする', async ({ page }) => {
  resetReplayTestState(environment());
  await page.setViewportSize({ width: 889, height: 864 });
  await gotoMain(page);
  await page.getByTestId('settings-button').click();
  await page.getByRole('radio', { name: 'すべての設定' }).click();
  await page.getByRole('tab', { name: '編集', exact: true }).click();
  await page.getByRole('button', { name: 'サムネイルデザインを編集' }).click();
  const editor = page.getByRole('dialog', { name: 'サムネイルデザイン' });
  const preview = editor.getByRole('region', { name: 'サムネイルプレビュー' });
  const properties = editor.getByRole('region', { name: '選択した要素の編集' });
  const elements = editor.getByRole('region', { name: '要素の管理' });
  await expect(preview.getByRole('img')).toBeVisible();
  await expect(preview.getByRole('combobox', { name: '表示パターン' })).toBeVisible();
  await expect(editor.getByText('1920 × 1080 px', { exact: true })).toHaveCount(0);
  await expect(preview.getByText(/を選択中$/)).toHaveCount(0);
  await expect(properties.getByRole('textbox', { name: '要素名', exact: true })).toBeVisible();
  await expect(properties.getByRole('slider', { name: /^不透明度/ })).toBeVisible();
  await editor.getByRole('button', { name: '背景をドラッグで移動' }).click();
  const background = preview.getByRole('button', { name: '背景の位置を調整' });
  const rect = await background.boundingBox();
  if (!rect) throw new Error('背景の移動面がありません');
  await page.mouse.move(rect.x + 10, rect.y + 10);
  await page.mouse.down();
  // 実際に押した状態でも、グローバルbutton装飾で画像をぼかしたり縮めたりしない。
  const style = await background.evaluate((el) => {
    const style = getComputedStyle(el);
    return {
      backdrop: style.backdropFilter,
      transform: style.transform,
      background: style.backgroundColor,
    };
  });
  expect(style).toEqual({ backdrop: 'none', transform: 'none', background: 'rgba(0, 0, 0, 0)' });
  await page.mouse.up();
  await page.keyboard.press('Escape');
  await preview
    .getByRole('button', { name: '要素の選択を解除', exact: true })
    .click({ position: { x: 5, y: 5 } });
  await expect(properties.getByRole('textbox', { name: '要素名', exact: true })).toBeHidden();
  await elements.getByRole('button', { name: 'マッチ画像', exact: true }).click();
  await preview.getByRole('combobox', { name: '表示パターン' }).selectOption('event');
  await expect(elements.getByRole('button', { name: 'マッチ画像', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true'
  );
  await preview
    .getByRole('button', { name: 'プレビューの余白で選択を解除' })
    .click({ position: { x: 3, y: 3 } });
  await expect(properties.getByRole('textbox', { name: '要素名', exact: true })).toBeHidden();
  await elements.getByRole('button', { name: '文字を追加' }).click();
  const content = properties.getByRole('textbox', { name: '文字内容' });
  await expect(content).toBeFocused();
  await properties.getByText('使えるテンプレート変数', { exact: true }).click();
  await properties.getByRole('button', { name: '{WIN}をコピー', exact: true }).click();
  await expect(properties.getByRole('status')).toHaveText('{WIN}をコピーしました');
  const contentRect = await content.boundingBox();
  const helpRect = await properties
    .getByText('使えるテンプレート変数', { exact: true })
    .boundingBox();
  expect(contentRect).not.toBeNull();
  expect(helpRect).not.toBeNull();
  expect(helpRect!.y).toBeLessThan(contentRect!.y + contentRect!.height + 45);
  await page.screenshot({ path: '../.tmp/thumbnail-polish/variables-889.png', fullPage: true });
});
