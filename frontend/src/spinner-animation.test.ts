import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readFrontendFile(relativePath: string): string {
  return readFileSync(resolve(import.meta.dirname, relativePath), 'utf8');
}

describe('spinner animation styles', () => {
  it('共通スピナーアニメーションをapp.cssに定義する', () => {
    const appCss = readFrontendFile('app.css');

    expect(appCss).toContain('@keyframes app-spinner-rotate');
    expect(appCss).toContain('.loading-spinner');
    expect(appCss).toContain('.spinner');
    expect(appCss).toContain('.spinner-small');
    expect(appCss).toMatch(/animation:\s*app-spinner-rotate\s+0\.8s\s+linear\s+infinite/);
  });

  it('主要な処理中表示が既知のスピナークラスを使っている', () => {
    expect(readFrontendFile('App.svelte')).toContain('class="loading-spinner"');
    expect(readFrontendFile('setup/components/SetupWizard.svelte')).toContain(
      'class="loading-spinner"'
    );
    expect(readFrontendFile('main/components/recording/BottomDrawer.svelte')).toContain(
      'class="spinner"'
    );
    expect(readFrontendFile('main/components/assets/RecordedDataList.svelte')).toContain(
      'class="spinner-small"'
    );
    expect(readFrontendFile('main/components/assets/EditedDataList.svelte')).toContain(
      'class="spinner-small"'
    );
    expect(readFrontendFile('main/components/progress/ProgressDialog.svelte')).toContain(
      'class="icon-spin"'
    );
  });

  it('05d79aで削除された回転定義を各コンポーネント内に維持する', () => {
    const app = readFrontendFile('App.svelte');
    const setupWizard = readFrontendFile('setup/components/SetupWizard.svelte');
    const bottomDrawer = readFrontendFile('main/components/recording/BottomDrawer.svelte');
    const recordedDataList = readFrontendFile('main/components/assets/RecordedDataList.svelte');
    const editedDataList = readFrontendFile('main/components/assets/EditedDataList.svelte');
    const progressDialog = readFrontendFile('main/components/progress/ProgressDialog.svelte');

    expect(app).toMatch(/\.loading-spinner\s*\{[\s\S]*animation:\s*spin\s+1s\s+linear\s+infinite/i);
    expect(app).toMatch(/@keyframes\s+spin/i);

    expect(setupWizard).toMatch(
      /\.loading-spinner\s*\{[\s\S]*animation:\s*spin\s+1s\s+linear\s+infinite/i
    );
    expect(setupWizard).toMatch(/@keyframes\s+spin/i);

    expect(bottomDrawer).toMatch(
      /\.spinner\s*\{[\s\S]*animation:\s*spin\s+0\.6s\s+linear\s+infinite/i
    );
    expect(bottomDrawer).toMatch(/@keyframes\s+spin/i);

    expect(recordedDataList).toMatch(
      /\.spinner-small\s*\{[\s\S]*animation:\s*spin\s+0\.6s\s+linear\s+infinite/i
    );
    expect(recordedDataList).toMatch(/@keyframes\s+spin/i);

    expect(editedDataList).toMatch(
      /\.spinner-small\s*\{[\s\S]*animation:\s*spin\s+0\.6s\s+linear\s+infinite/i
    );
    expect(editedDataList).toMatch(/@keyframes\s+spin/i);

    expect(progressDialog).toMatch(
      /(?::global\()?\.\s*icon-spin[\s\S]*animation:\s*progress-icon-spin\s+\d*\.?\d+s\s+linear\s+infinite/i
    );
    expect(progressDialog).toMatch(/@keyframes\s+progress-icon-spin/i);
  });
});
