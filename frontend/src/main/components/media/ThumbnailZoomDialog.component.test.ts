import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import ThumbnailZoomDialog from './ThumbnailZoomDialog.svelte';

describe('ThumbnailZoomDialog', () => {
  it('サムネイルURLとタイトルが設定される', () => {
    render(ThumbnailZoomDialog, {
      props: {
        visible: true,
        imageUrl: '/api/thumbnails/test.png',
        imageTitle: 'テストサムネイル',
      },
    });

    expect(screen.queryByText('テストサムネイル')).toBeInTheDocument();
  });

  it('画像要素が正しいソースURLを持つ', () => {
    render(ThumbnailZoomDialog, {
      props: {
        visible: true,
        imageUrl: '/api/thumbnails/test.png',
        imageTitle: 'テストサムネイル',
      },
    });

    const img = screen.getByRole('img', { name: 'テストサムネイル' });
    expect(img).toHaveAttribute('src', '/api/thumbnails/test.png');
    expect(img).toHaveAttribute('alt', 'テストサムネイル');
  });

  it('visibleがfalseの場合、ダイアログは表示されない', () => {
    render(ThumbnailZoomDialog, {
      props: {
        visible: false,
        imageUrl: '/api/thumbnails/test.png',
        imageTitle: 'テストサムネイル',
      },
    });

    expect(screen.queryByText('テストサムネイル')).not.toBeInTheDocument();
  });

  it('閉じるボタンでダイアログが閉じる', async () => {
    render(ThumbnailZoomDialog, {
      props: {
        visible: true,
        imageUrl: '/api/thumbnails/test.png',
        imageTitle: 'テストサムネイル',
      },
    });

    const closeButtons = screen.getAllByRole('button');
    const closeButton = closeButtons.find((btn) => {
      const ariaLabel = btn.getAttribute('aria-label');
      return ariaLabel === 'Close' || ariaLabel === '閉じる';
    });

    expect(closeButton).toBeDefined();
    if (closeButton) {
      await fireEvent.click(closeButton);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    }
  });
});
