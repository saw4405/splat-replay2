/**
 * API共通ユーティリティ
 *
 * 責務：
 * - HTTPヘッダー定義
 * - エラーハンドリング補助関数
 */

export const JSON_HEADERS: HeadersInit = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
};

/**
 * レスポンスからテキストを安全に読み取る
 */
export async function safeReadText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return '';
  }
}
