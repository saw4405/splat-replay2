import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readSettingsDialog(): string {
  return readFileSync(resolve(import.meta.dirname, 'SettingsDialog.svelte'), 'utf8');
}

describe('SettingsDialog layout', () => {
  it('先頭の動作タブが選択されても上端が見切れない余白を持つ', () => {
    const settingsDialog = readSettingsDialog();
    const tabsRule = settingsDialog.match(/\.tabs\s*\{[\s\S]*?\n\s*\}/)?.[0] ?? '';

    expect(tabsRule).toContain('padding: 0.25rem 0.5rem;');
  });
});
