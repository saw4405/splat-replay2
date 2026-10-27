import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { newThumbnailElement, type ThumbnailDesign } from '../../api/thumbnailDesign';
import ThumbnailDesignDialog from './ThumbnailDesignDialog.svelte';

function initialDesign(): ThumbnailDesign {
  return {
    version: 1,
    background: { source: 'result', asset: '', x: 0, y: 0, scale: 1 },
    elements: [
      {
        ...newThumbnailElement('text'),
        id: 'wins',
        source: 'win_lose',
        name: '勝敗',
        template: '{WIN} - {LOSE}',
        x: 458,
        y: 100,
      },
    ],
  };
}

describe('サムネイルデザイン', () => {
  let previews: ThumbnailDesign[];
  let failPreview = false;
  beforeEach(() => {
    previews = [];
    failPreview = false;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string, init?: RequestInit) => {
        if (input.endsWith('/preview')) {
          const data = JSON.parse(init?.body as string) as { design: ThumbnailDesign };
          previews.push(data.design);
          return failPreview
            ? new Response(JSON.stringify({ detail: 'テンプレートを確認してください' }), {
                status: 422,
              })
            : new Response(
                JSON.stringify({
                  image: 'data:image/png;base64,cG5n',
                  layout: Object.fromEntries(
                    data.design.elements.map((e) => [
                      e.id,
                      { x: e.x, y: e.y, width: e.width || 100, height: e.height || 50 },
                    ])
                  ),
                })
              );
        }
        return new Response(
          JSON.stringify({
            default_design: initialDesign(),
            assets: [
              { id: 'Paintball_Beta.otf', name: 'Paintball', kind: 'font', protected: true },
            ],
            variables: { WIN: 4, LOSE: 3 },
          })
        );
      })
    );
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:thumbnail');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('適用で生成画像を確認し、採用するまで親へ渡さない', async () => {
    const user = userEvent.setup();
    const onapply = vi.fn();
    const design = initialDesign();
    render(ThumbnailDesignDialog, { open: true, design, onapply });
    await user.type(await screen.findByLabelText('テンプレート'), ' wins');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '適用', exact: true })).toBeEnabled()
    );
    await user.click(screen.getByRole('button', { name: '適用', exact: true }));
    expect(
      await screen.findByAltText('実際の生成処理によるサンプルサムネイル')
    ).toBeInTheDocument();
    expect(onapply).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: '編集に戻る' }));
    expect(await screen.findByLabelText('テンプレート')).toHaveValue('{WIN} - {LOSE} wins');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '適用', exact: true })).toBeEnabled()
    );
    await user.click(screen.getByRole('button', { name: '適用', exact: true }));
    await user.click(await screen.findByRole('button', { name: 'このデザインを使う' }));
    expect(onapply).toHaveBeenCalledWith(
      expect.objectContaining({
        elements: [expect.objectContaining({ template: '{WIN} - {LOSE} wins' })],
      })
    );
    expect(design.elements[0].template).toBe('{WIN} - {LOSE}');
  });

  it('要素の追加・位置調整・削除を反映し、キャンセルで元のデザインを維持する', async () => {
    const user = userEvent.setup();
    const onapply = vi.fn();
    const design = initialDesign();
    render(ThumbnailDesignDialog, { open: true, design, onapply });
    await user.click(await screen.findByRole('button', { name: '図形を追加' }));
    await fireEvent.input(screen.getByLabelText('X', { exact: true }), {
      target: { value: '500' },
    });
    await waitFor(() => expect(previews.at(-1)?.elements.at(-1)?.x).toBe(500));
    await fireEvent.keyDown(await screen.findByRole('button', { name: '図形の位置を調整' }), {
      key: 'ArrowRight',
      shiftKey: true,
    });
    expect(screen.getByLabelText('X', { exact: true })).toHaveValue(510);
    await user.click(screen.getByRole('button', { name: '要素を削除' }));
    expect(screen.queryByRole('button', { name: '図形の位置を調整' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'キャンセル', exact: true }));
    expect(onapply).not.toHaveBeenCalled();
    expect(design.elements).toHaveLength(1);
  });

  it('背景の切り替えを常に表示し、追加したレイヤーを元に戻してやり直せる', async () => {
    const user = userEvent.setup();
    render(ThumbnailDesignDialog, { open: true, design: initialDesign(), onapply: vi.fn() });
    const background = await screen.findByRole('combobox', { name: '背景', exact: true });
    expect(background).toHaveValue('result');
    expect(screen.queryByText('サンプルで編集中')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '図形を追加' }));
    expect(screen.getByRole('combobox', { name: '図形', exact: true })).toBeVisible();
    await user.click(screen.getByRole('button', { name: '元に戻す' }));
    expect(screen.queryByRole('combobox', { name: '図形', exact: true })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'やり直す' }));
    expect(screen.getByRole('combobox', { name: '図形', exact: true })).toBeVisible();
  });

  it('文字追加直後に内容を入力でき、要素を切り替えても内容欄へ戻れる', async () => {
    const user = userEvent.setup();
    render(ThumbnailDesignDialog, { open: true, design: initialDesign(), onapply: vi.fn() });
    await user.click(await screen.findByRole('button', { name: '文字を追加' }));
    const content = await screen.findByLabelText('文字内容');
    await waitFor(() => expect(content).toHaveFocus());
    await user.clear(content);
    await user.type(content, '今日のベストプレイ {{WIN}勝');
    await waitFor(() =>
      expect(previews.at(-1)?.elements.at(-1)?.template).toBe('今日のベストプレイ {WIN}勝')
    );
    expect(screen.getByRole('region', { name: '背景の設定' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: '選択した要素の編集' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '要素の選択を解除', exact: true }));
    await user.click(screen.getByRole('button', { name: '勝敗', exact: true }));
    expect(screen.getByRole('textbox', { name: 'テンプレート', exact: true })).not.toHaveFocus();
  });

  it('背景の移動モードと倍率を同じパネルで操作し、Escで要素編集へ戻る', async () => {
    const user = userEvent.setup();
    render(ThumbnailDesignDialog, { open: true, design: initialDesign(), onapply: vi.fn() });
    await user.click(await screen.findByRole('button', { name: '背景をドラッグで移動' }));
    const handle = screen.getByRole('button', { name: '背景の位置を調整' });
    await fireEvent.keyDown(handle, { key: 'ArrowRight', shiftKey: true });
    await fireEvent.input(screen.getByRole('slider', { name: '背景の倍率' }), {
      target: { value: '2' },
    });
    await waitFor(() =>
      expect(previews.at(-1)?.background).toMatchObject({ x: 10, y: 0, scale: 2 })
    );
    await fireEvent.keyDown(handle, { key: 'Escape' });
    expect(screen.queryByRole('button', { name: '背景の位置を調整' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '背景の位置・倍率を戻す' }));
    expect(screen.getByRole('spinbutton', { name: '背景のX' })).toHaveValue(0);
    expect(screen.getByRole('slider', { name: '背景の倍率' })).toHaveValue('1');
  });

  it('自動プレビュー中でも適用を優先し、遅れて返った表示で生成確認を消さない', async () => {
    const user = userEvent.setup();
    const originalFetch = globalThis.fetch;
    let previewsStarted = 0;
    let release = () => {};
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string, init?: RequestInit) => {
        if (input.endsWith('/preview') && ++previewsStarted === 1) await pending;
        return originalFetch(input, init);
      })
    );
    render(ThumbnailDesignDialog, { open: true, design: initialDesign(), onapply: vi.fn() });
    await waitFor(() => expect(previewsStarted).toBe(1));
    try {
      expect(screen.getByRole('button', { name: '適用', exact: true })).toBeEnabled();
      await user.click(screen.getByRole('button', { name: '適用', exact: true }));
      expect(await screen.findByRole('button', { name: 'このデザインを使う' })).toBeInTheDocument();
    } finally {
      release();
    }
    await waitFor(() => expect(previews).toHaveLength(2));
    expect(screen.getByRole('button', { name: 'このデザインを使う' })).toBeInTheDocument();
  });

  it('生成に失敗した場合はエラーを表示し、採用に進めない', async () => {
    failPreview = true;
    const user = userEvent.setup();
    const onapply = vi.fn();
    render(ThumbnailDesignDialog, { open: true, design: initialDesign(), onapply });
    await user.click(await screen.findByRole('button', { name: '適用', exact: true }));
    expect(await screen.findByRole('alert')).toHaveTextContent('テンプレートを確認してください');
    expect(screen.queryByRole('button', { name: 'このデザインを使う' })).not.toBeInTheDocument();
    expect(onapply).not.toHaveBeenCalled();
  });
});
