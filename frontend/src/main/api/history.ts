/**
 * 対戦履歴API
 *
 * 責務：
 * - 対戦履歴の一覧取得
 */

import type { BattleHistoryEntry } from './types.ts';
import { JSON_HEADERS } from './utils.ts';

/**
 * 対戦履歴一覧を取得
 */
export async function fetchBattleHistory(): Promise<BattleHistoryEntry[]> {
  const response = await fetch('/api/history/battle', {
    headers: JSON_HEADERS,
  });

  if (!response.ok) {
    throw new Error(`対戦履歴の取得に失敗しました: ${response.status}`);
  }

  const body = await response.json();
  return body.records as BattleHistoryEntry[];
}
