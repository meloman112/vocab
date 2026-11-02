import { initData } from '../lib/telegram';
import type {
  AdminSummary,
  AdminWord,
  Card,
  Leaderboard,
  Me,
  QuizCard,
  QuizSource,
  Rating,
  ReportedWord,
  ReportReason,
  ReviewResult,
  Stats,
  WordEdit,
} from './types';

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
  // 204 — тела нет, и json() упал бы на пустой строке.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
}

export const api = {
  queue: () => request<{ cards: Card[] }>('/queue'),

  /** Новые слова из общего словаря — сервер сразу заводит на них карточки. */
  discover: () => request<{ cards: Card[] }>('/discover', { method: 'POST' }),

  stats: () => request<Stats>('/stats'),

  leaderboard: () => request<Leaderboard>('/leaderboard'),

  review: (cardId: number, rating: Rating) =>
    send<ReviewResult>('POST', '/review', { card_id: cardId, rating }),

  quiz: (mode: QuizSource, limit: number) =>
    request<{ cards: QuizCard[] }>(`/quiz?mode=${mode}&limit=${limit}`),

  report: (wordId: number, reason: ReportReason) =>
    send<void>('POST', '/reports', { word_id: wordId, reason }),

  me: () => request<Me>('/me'),

  admin: {
    summary: () => request<AdminSummary>('/admin/summary'),
    reports: () => request<ReportedWord[]>('/admin/reports'),
    dismiss: (wordId: number) => send<void>('POST', `/admin/reports/${wordId}/dismiss`),
    words: (query: string) => request<AdminWord[]>(`/admin/words?q=${encodeURIComponent(query)}`),
    save: (wordId: number, edit: WordEdit) => send<AdminWord>('PUT', `/admin/words/${wordId}`, edit),
  },
};
