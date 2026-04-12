import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readVideoPreviewContainer(): string {
  return readFileSync(resolve(import.meta.dirname, 'VideoPreviewContainer.svelte'), 'utf8');
}

describe('VideoPreviewContainer layout spacing', () => {
  it('uses the main layout available height instead of adding its own outer margin', () => {
    const videoPreviewContainer = readVideoPreviewContainer();

    expect(videoPreviewContainer).toContain(
      'max-height: var(--main-preview-available-height, calc(100vh - 180px));'
    );
    expect(videoPreviewContainer).toMatch(/\.preview-container\s*\{[\s\S]*margin:\s*0;/i);
  });
});
