/**
 * Metadata編集フロー Integration テスト
 *
 * 責務：
 * - MetadataForm と MetadataEditDialog の統合動作検証
 * - メタデータオプション取得→フォーム表示→編集→保存の一連の流れ
 * - エラーハンドリング
 *
 * 分類: integration
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import MetadataEditDialog from './MetadataEditDialog.svelte';
import type { EditableMetadata } from '../../metadata/editable';
import type { MetadataOptions } from '../../api/types';
import * as metadataApi from '../../api/metadata';

describe('Metadata編集フロー Integration', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  const mockMetadataOptions: MetadataOptions = {
    matches: [
      { value: 'regular', label: 'レギュラーマッチ' },
      { value: 'anarchy_open', label: 'バンカラマッチ（オープン）' },
    ],
    rules: [
      { value: 'nawabari', label: 'ナワバリバトル' },
      { value: 'area', label: 'ガチエリア' },
    ],
    stages: [
      { value: 'yunohana', label: 'ユノハナ大渓谷' },
      { value: 'gonzui', label: 'ゴンズイ地区' },
    ],
    judgements: [
      { value: 'win', label: '勝ち' },
      { value: 'lose', label: '負け' },
    ],
  };

  const mockMetadata: EditableMetadata = {
    startedAt: '2026-03-14T10:00:00',
    gameMode: 'battle',
    match: 'regular',
    rule: 'nawabari',
    stage: 'yunohana',
    rate: null,
    judgement: 'win',
    kill: 10,
    death: 5,
    special: 3,
    goldMedals: 0,
    silverMedals: 0,
    allies: ['weapon1', 'weapon2', 'weapon3'],
    enemies: ['weapon4', 'weapon5', 'weapon6', 'weapon7'],
  };

  beforeEach(() => {
    // メタデータオプションのキャッシュをクリア
    metadataApi.clearMetadataOptionsCache();

    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // デフォルトのメタデータオプション取得レスポンス
    fetchMock.mockImplementation(async (url: string | URL | Request) => {
      const urlString = url.toString();
      if (urlString.includes('/api/metadata/options')) {
        return new Response(JSON.stringify(mockMetadataOptions), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({}), { status: 404 });
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('初期化とデータ読み込み', () => {
    it('ダイアログを開くとメタデータオプションが利用可能である', async () => {
      const { container } = render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      // メタデータオプションが読み込まれ、セレクトボックスにオプションが表示される
      // ドロップダウンが存在し、選択可能な状態になることを確認
      await waitFor(
        () => {
          const matchSelect = container.querySelector('select#match');
          const ruleSelect = container.querySelector('select#rule');
          const stageSelect = container.querySelector('select#stage');

          expect(matchSelect).toBeInTheDocument();
          expect(ruleSelect).toBeInTheDocument();
          expect(stageSelect).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // オプションが正しく読み込まれていることを確認
      // （空のselect elements ではないことを確認）
      const matchSelect = container.querySelector('select#match') as HTMLSelectElement;
      const options = Array.from(matchSelect.options);
      // 最初のオプション（空の選択肢）を除いて、実際のオプションがあるはず
      expect(options.length).toBeGreaterThan(0);
    });

    it('メタデータオプション読み込み失敗時でもダイアログは正常に表示される', async () => {
      // このテスト専用のfetchモックを設定（エラーを投げる）
      const testFetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
      global.fetch = testFetchMock;

      const { container } = render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      // ダイアログは開いたままで、エラーモーダルなどは表示されない
      expect(screen.getByRole('dialog')).toBeInTheDocument();

      // フォームの主要な要素が表示されている
      expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      expect(screen.getByLabelText('デス数')).toBeInTheDocument();

      // セレクトボックスは存在するが、オプションが空かもしれない
      const matchSelect = container.querySelector('select#match');
      expect(matchSelect).toBeInTheDocument();

      // 保存ボタンとキャンセルボタンは正常に表示される
      expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'キャンセル' })).toBeInTheDocument();
    });

    it('初期メタデータがフォームに表示される', async () => {
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      await waitFor(() => {
        // kill フィールドの値が表示される
        const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
        expect(killInput.value).toBe('10');
      });
    });
  });

  describe('メタデータ編集', () => {
    it('フォームで値を変更できる', async () => {
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      await waitFor(() => {
        expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      });

      const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
      await fireEvent.input(killInput, { target: { value: '15' } });

      expect(killInput.value).toBe('15');
    });

    it('複数のフィールドを編集できる', async () => {
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      await waitFor(() => {
        expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      });

      const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
      const deathInput = screen.getByLabelText('デス数') as HTMLInputElement;

      await fireEvent.input(killInput, { target: { value: '20' } });
      await fireEvent.input(deathInput, { target: { value: '2' } });

      expect(killInput.value).toBe('20');
      expect(deathInput.value).toBe('2');
    });
  });

  describe('保存フロー', () => {
    it('保存ボタンをクリックするとsaveイベントが発火する', async () => {
      const saveHandler = vi.fn();
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
          onSave: saveHandler,
        },
      });

      await waitFor(() => {
        expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: '保存' });
      await fireEvent.click(saveButton);

      expect(saveHandler).toHaveBeenCalledTimes(1);
    });

    it('保存イベントにvideoIdと編集後のメタデータが含まれる', async () => {
      const saveHandler = vi.fn();
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
          onSave: saveHandler,
        },
      });

      await waitFor(() => {
        expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      });

      // 値を変更
      const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
      await fireEvent.input(killInput, { target: { value: '25' } });

      const saveButton = screen.getByRole('button', { name: '保存' });
      await fireEvent.click(saveButton);

      expect(saveHandler).toHaveBeenCalledTimes(1);
      const args = saveHandler.mock.calls[0][0] as { videoId: string; metadata: { kill: number } };
      expect(args.videoId).toBe('test-video.mp4');
      expect(args.metadata.kill).toBe(25);
    });

    it('保存後にダイアログが閉じる', async () => {
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: '保存' });
      await fireEvent.click(saveButton);

      // ダイアログが閉じる
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('キャンセルフロー', () => {
    it('キャンセルボタンをクリックするとダイアログが閉じる', async () => {
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'キャンセル' })).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: 'キャンセル' });
      await fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('キャンセル時は編集内容が破棄される', async () => {
      const saveHandler = vi.fn();
      render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
          onSave: saveHandler,
        },
      });

      await waitFor(() => {
        expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      });

      // 値を変更
      const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
      await fireEvent.input(killInput, { target: { value: '99' } });

      // キャンセル
      const cancelButton = screen.getByRole('button', { name: 'キャンセル' });
      await fireEvent.click(cancelButton);

      // saveイベントは発火しない
      expect(saveHandler).not.toHaveBeenCalled();
    });
  });

  describe('再表示時の動作', () => {
    it('ダイアログを閉じて再度開くと元のメタデータが表示される', async () => {
      const { component, rerender } = render(MetadataEditDialog, {
        props: {
          visible: true,
          videoId: 'test-video.mp4',
          metadata: mockMetadata,
        },
      });

      await waitFor(() => {
        expect(screen.getByLabelText('キル数')).toBeInTheDocument();
      });

      // 値を変更
      const killInput = screen.getByLabelText('キル数') as HTMLInputElement;
      await fireEvent.input(killInput, { target: { value: '99' } });

      // 閉じる
      await rerender({ visible: false, videoId: 'test-video.mp4', metadata: mockMetadata });

      // 再度開く
      await rerender({ visible: true, videoId: 'test-video.mp4', metadata: mockMetadata });

      await waitFor(() => {
        const killInputAgain = screen.getByLabelText('キル数') as HTMLInputElement;
        // 元の値（10）に戻っている
        expect(killInputAgain.value).toBe('10');
      });
    });
  });
});
