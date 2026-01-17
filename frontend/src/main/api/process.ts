import { JSON_HEADERS, safeReadText } from './utils';

export const processApi = {
  start: async (): Promise<void> => {
    const response = await fetch('/api/process/start', {
      method: 'POST',
      headers: JSON_HEADERS,
    });
    if (!response.ok) {
      const detail = await safeReadText(response);
      throw new Error(detail || '自動処理の開始に失敗しました');
    }
  },
  startSleep: async (): Promise<void> => {
    const response = await fetch('/api/process/sleep/start', {
      method: 'POST',
      headers: JSON_HEADERS,
    });
    if (!response.ok) {
      const detail = await safeReadText(response);
      throw new Error(detail || '自動スリープの開始に失敗しました');
    }
  },
};
