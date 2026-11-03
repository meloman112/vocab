import { initData } from '../lib/telegram';
import type {
  AdminSummary,
  AdminWord,
  Card,
  CommonMistake,
  GrammarAttempt,
  GrammarContent,
  GrammarProgress,
  Leaderboard,
  PdfExercise,
  Student,
  StudentDetail,
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
    // (открыли вне Telegram) отличался от 500. Исключение — 502 от
    // Telegram при отправке PDF: там detail объясняет, что нажать Start.
    const detail = response.status === 502 ? ((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail : null;
    throw new Error(typeof detail === 'string' ? detail : `Запрос ${path} вернул ${response.status}`);
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

  grammar: {
    content: () => request<GrammarContent>('/grammar/content'),
    progress: () => request<GrammarProgress>('/grammar/progress'),
    attempt: (attempt: GrammarAttempt) => send<void>('POST', '/grammar/attempts', attempt),
    import: (items: Record<string, unknown>) => send<{ imported: number }>('POST', '/grammar/import', { items }),
    pdf: (exercises: PdfExercise[]) => send<void>('POST', '/grammar/pdf', { exercises }),
  },

  teacher: {
    students: () => request<Student[]>('/teacher/students'),
    student: (userId: number) => request<StudentDetail>(`/teacher/students/${userId}`),
    accept: (mistakeId: number) => send<void>('POST', `/teacher/mistakes/${mistakeId}/accept`),
    common: () => request<CommonMistake[]>('/teacher/mistakes/common'),
  },

  admin: {
    summary: () => request<AdminSummary>('/admin/summary'),
    reports: () => request<ReportedWord[]>('/admin/reports'),
    dismiss: (wordId: number) => send<void>('POST', `/admin/reports/${wordId}/dismiss`),
    words: (query: string) => request<AdminWord[]>(`/admin/words?q=${encodeURIComponent(query)}`),
    save: (wordId: number, edit: WordEdit) => send<AdminWord>('PUT', `/admin/words/${wordId}`, edit),
  },
};
