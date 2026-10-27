import { cleanup, render, screen, fireEvent } from '@testing-library/svelte';
import { afterEach, expect, it, vi } from 'vitest';
import ThumbnailCanvas from './ThumbnailCanvas.svelte';
import { newThumbnailElement, type ThumbnailDesign } from '../../api/thumbnailDesign';

afterEach(cleanup);
const design: ThumbnailDesign = {
  version: 1,
  background: { source: 'result', asset: '', x: 0, y: 0, scale: 1 },
  elements: [
    {
      ...newThumbnailElement('text'),
      id: 'wins',
      source: 'win_lose',
      name: '勝敗',
      template: '{WIN} - {LOSE}',
      font_size: 120,
      x: 458,
      y: 100,
      center: true,
    },
  ],
};
const callbacks = { onselect: vi.fn(), onmove: vi.fn(), onsample: vi.fn(), picking: false };

it('文字の選択範囲はサーバーの実描画領域に一致する', () => {
  const layout = { wins: { x: 312, y: 68, width: 300, height: 104 } };
  render(ThumbnailCanvas, {
    design,
    imageUrl: 'blob:preview',
    selectedId: 'wins',
    layout,
    ...callbacks,
  });
  const handle = screen.getByRole('button', { name: '勝敗の位置を調整' });
  expect(handle.style.left).toBe('16.25%');
  expect(handle.style.width).toBe('15.625%');
});

it('実際に描かれなかった要素に選択領域を作らない', () => {
  render(ThumbnailCanvas, {
    design,
    imageUrl: 'blob:preview',
    selectedId: '',
    layout: {},
    ...callbacks,
  });
  expect(screen.queryByRole('button', { name: '勝敗の位置を調整' })).not.toBeInTheDocument();
});

it('通常モードの空白クリックで選択を解除し、背景移動中は解除操作と競合しない', async () => {
  const select = vi.fn();
  const view = render(ThumbnailCanvas, {
    design,
    layout: { wins: { x: 312, y: 68, width: 300, height: 104 } },
    imageUrl: 'blob:preview',
    selectedId: 'wins',
    ...callbacks,
    onselect: select,
  });
  await fireEvent.click(screen.getByRole('button', { name: '要素の選択を解除' }));
  expect(select).toHaveBeenCalledWith('');
  await view.rerender({ backgroundMoving: true });
  expect(screen.queryByRole('button', { name: '要素の選択を解除' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '背景の位置を調整' })).toBeInTheDocument();
});
