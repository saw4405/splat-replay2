import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readMainApp(): string {
  return readFileSync(resolve(import.meta.dirname, 'MainApp.svelte'), 'utf8');
}

describe('MainApp layout spacing', () => {
  it('reserves explicit space between the title, preview, and bottom drawer', () => {
    const mainApp = readMainApp();

    expect(mainApp).toContain('--app-title-preview-gap: 1.5rem;');
    expect(mainApp).toContain('--preview-drawer-gap: 1.5rem;');
    expect(mainApp).toContain('--bottom-drawer-reserved-height: 5.75rem;');
    expect(mainApp).toContain('gap: var(--app-title-preview-gap);');
    expect(mainApp).toContain(
      'calc(var(--bottom-drawer-reserved-height) + var(--preview-drawer-gap))'
    );
  });

  it('does not clip the app title glow', () => {
    const mainApp = readMainApp();
    const titleRule = mainApp.match(/h1\s*\{[\s\S]*?\n\s*\}/)?.[0] ?? '';

    expect(titleRule).toContain('text-shadow:');
    expect(titleRule).not.toContain('overflow: hidden;');
    expect(titleRule).not.toContain('text-overflow: ellipsis;');
  });
});
