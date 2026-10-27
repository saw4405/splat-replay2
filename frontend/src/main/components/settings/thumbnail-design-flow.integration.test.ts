import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import SettingsDialog from './SettingsDialog.svelte';
import { newThumbnailElement, type ThumbnailDesign } from '../../api/thumbnailDesign';

let saved: ThumbnailDesign;
let writes: ThumbnailDesign[];

beforeEach(() => {
  writes = [];
  saved = {
    version: 1,
    background: { source: 'result', asset: '', x: 0, y: 0, scale: 1 },
    elements: [
      {
        ...newThumbnailElement('text'),
        id: 'wins',
        name: '勝敗',
        source: 'win_lose',
        template: '{WIN} - {LOSE}',
      },
    ],
  };
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:thumbnail');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/preview'))
        return new Response(JSON.stringify({ image: 'data:image/png;base64,cG5n', layout: {} }));
      if (url === '/api/thumbnail-design')
        return new Response(
          JSON.stringify({ default_design: saved, assets: [], variables: { WIN: 4, LOSE: 3 } })
        );
      if (init?.method === 'PUT') {
        const body = JSON.parse(init.body as string) as {
          sections: { values: { thumbnail_design: ThumbnailDesign } }[];
        };
        saved = body.sections[0].values.thumbnail_design;
        writes.push(saved);
        return new Response('{}');
      }
      return new Response(
        JSON.stringify({
          sections: [
            {
              id: 'video_edit',
              label: '動画編集',
              fields: [
                {
                  id: 'thumbnail_design',
                  label: 'サムネイルデザイン',
                  type: 'thumbnail_design',
                  value: saved,
                  user_editable: true,
                  display_level: 'advanced',
                  requirement: 'optional',
                },
              ],
            },
          ],
        })
      );
    })
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function editAndAdopt(): Promise<void> {
  const user = userEvent.setup();
  await user.click(await screen.findByRole('radio', { name: 'すべての設定' }));
  await user.click(await screen.findByRole('button', { name: 'サムネイルデザインを編集' }));
  const dialog = await screen.findByRole('dialog', { name: 'サムネイルデザイン' });
  await user.type(await within(dialog).findByLabelText('テンプレート'), ' edited');
  await waitFor(() =>
    expect(within(dialog).getByRole('button', { name: '適用', exact: true })).toBeEnabled()
  );
  await user.click(within(dialog).getByRole('button', { name: '適用', exact: true }));
  await user.click(await within(dialog).findByRole('button', { name: 'このデザインを使う' }));
  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'サムネイルデザイン' })).not.toBeInTheDocument()
  );
}

it('採用したデザインは親の保存で初めて更新要求に含まれる', async () => {
  render(SettingsDialog, { open: true });
  await editAndAdopt();
  expect(writes).toHaveLength(0);
  await userEvent.click(screen.getByRole('button', { name: '保存', exact: true }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].elements[0].template).toBe('{WIN} - {LOSE} edited');
});

it('子で採用しても親でキャンセルすれば保存しない', async () => {
  render(SettingsDialog, { open: true });
  await editAndAdopt();
  await userEvent.click(screen.getByRole('button', { name: 'キャンセル', exact: true }));
  expect(writes).toHaveLength(0);
  expect(saved.elements[0].template).toBe('{WIN} - {LOSE}');
});
