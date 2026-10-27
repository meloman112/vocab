import { initData } from '../lib/telegram';
import type { Card, Rating, ReviewResult } from './types';

/**
 * API и статика отдаются одним приложением, поэтому базового URL нет:
 * относительный путь всегда попадает туда, откуда пришла страница.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': initData,
      ...init?.headers,
    },
  });

  if (!response.ok) {
    // Текст ошибки не показываем как есть: там бывает detail от FastAPI,
    // пользователю от него пользы нет. Статус в сообщении — чтобы 401
    // (открыли вне Telegram) отличался от 500.
    throw new Error(`Запрос ${path} вернул ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  queue: () => request<{ cards: Card[] }>('/queue'),

  /** Новые слова из общего словаря — сервер сразу заводит на них карточки. */
  discover: () => request<{ cards: Card[] }>('/discover', { method: 'POST' }),

  review: (cardId: number, rating: Rating) =>
    request<ReviewResult>('/review', {
      method: 'POST',
      body: JSON.stringify({ card_id: cardId, rating }),
    }),
};
