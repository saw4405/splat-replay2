import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readBottomDrawer(): string {
  return readFileSync(resolve(import.meta.dirname, 'BottomDrawer.svelte'), 'utf8');
}

describe('BottomDrawer tab width styles', () => {
  it('戦績タブのアイコン幅と情報幅を固定して録画済・編集済と揃える', () => {
    const bottomDrawer = readBottomDrawer();

    expect(bottomDrawer).toMatch(
      /\.tab-icon\s*\{[\s\S]*width:\s*1\.5rem;[\s\S]*text-align:\s*center;[\s\S]*flex-shrink:\s*0;/i
    );
    expect(bottomDrawer).toMatch(/\.tab-info\s*\{[\s\S]*min-width:\s*3\.25rem;/i);
  });
});
