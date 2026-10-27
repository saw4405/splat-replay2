import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import ThumbnailTemplateHints from './ThumbnailTemplateHints.svelte';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('展開したヒントから波括弧込みの変数をコピーする', async () => {
  const user = userEvent.setup();
  const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
  render(ThumbnailTemplateHints, { variables: { WIN: 4, RATE_LABEL: 'XP: ' } });
  expect(screen.getByText('使えるテンプレート変数').closest('details')).not.toHaveAttribute('open');
  await user.click(screen.getByText('使えるテンプレート変数'));
  await user.click(screen.getByRole('button', { name: '{WIN}をコピー' }));
  expect(write).toHaveBeenCalledWith('{WIN}');
  expect(await screen.findByText('{WIN}をコピーしました')).toBeInTheDocument();
});

it('コピーに失敗した場合は成功と表示せず、手動コピーできる文字列を選択する', async () => {
  const user = userEvent.setup();
  vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));
  render(ThumbnailTemplateHints, { variables: { WIN: 4 } });
  await user.click(screen.getByText('使えるテンプレート変数'));
  await user.click(screen.getByRole('button', { name: '{WIN}をコピー' }));
  const fallback = (await screen.findByRole('textbox', {
    name: 'コピーする変数',
  })) as HTMLInputElement;
  expect(fallback).toHaveValue('{WIN}');
  expect(fallback).toHaveFocus();
  expect(fallback.selectionStart).toBe(0);
  expect(fallback.selectionEnd).toBe(5);
  expect(screen.getByRole('status')).toHaveTextContent('コピーできませんでした');
  expect(screen.queryByText('{WIN}をコピーしました')).not.toBeInTheDocument();
});
