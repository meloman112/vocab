import { apiUrl, initData } from '../lib/telegram';
import type {
  AdminSummary,
  AdminWord,
  Card,
  CommonMistake,
  GrammarAttempt,
  GrammarContent,
  GrammarProgress,
  Leaderboard,
  Lookup,
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
  ConvertedLine,
  SchoolClass,
  StudentTest,
  TestPreview,
  TestReport,
  TestRow,
} from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
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
    // Telegram при отправке PDF: там detail объясняет, что нажать Start,
    // и 422 от перевода — «не знаю такого слова». Тесты учителя объясняют
    // 404/409/410 по-русски: «срок прошёл», «тест уже сдан».
    const detail = [404, 409, 410, 422, 502].includes(response.status) ?((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail : null;
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
  discover: (deck?: string) =>
    request<{ cards: Card[] }>(deck ? `/discover?deck=${encodeURIComponent(deck)}` : '/discover', { method: 'POST' }),

  stats: () => request<Stats>('/stats'),

  leaderboard: () => request<Leaderboard>('/leaderboard'),

  review: (cardId: number, rating: Rating) =>
    send<ReviewResult>('POST', '/review', { card_id: cardId, rating }),

  known: (cardId: number) => send<void>('PUT', `/cards/${cardId}/known`),

  unknown: (cardId: number) => send<void>('DELETE', `/cards/${cardId}/known`),

  quiz: (mode: QuizSource, limit: number) =>
    request<{ cards: QuizCard[] }>(`/quiz?mode=${mode}&limit=${limit}`),

  report: (wordId: number, reason: ReportReason) =>
    send<void>('POST', '/reports', { word_id: wordId, reason }),

  me: () => request<Me>('/me'),

  /** Перевод выделенного слова; карточку не заводит. */
  lookup: (text: string, signal?: AbortSignal) =>
    request<Lookup>(`/lookup?text=${encodeURIComponent(text)}`, { signal }),
  saveWord: (wordId: number) => send<void>('POST', `/words/${wordId}/card`),

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
    classes: () => request<SchoolClass[]>('/teacher/classes'),
    createClass: (name: string) => send<SchoolClass>('POST', '/teacher/classes', { name }),
    tests: () => request<TestRow[]>('/teacher/tests'),
    test: (id: number) => request<TestReport>(`/teacher/tests/${id}`),
    preview: (text: string, signal?: AbortSignal) =>
      request<TestPreview>('/teacher/tests/preview', { method: 'POST', body: JSON.stringify({ text }), signal }),
    convert: (source: { text?: string; docx?: string }) => send<ConvertedLine[]>('POST', '/teacher/tests/convert', source),
    createTest: (test: { title: string; class_id: number; due: string; text: string }) =>
      send<{ id: number; sent: number }>('POST', '/teacher/tests', test),
    acceptAnswer: (testId: number, gap: number, answer: string) =>
      send<void>('POST', `/teacher/tests/${testId}/accept`, { gap, answer }),
    deleteTest: (id: number) => send<void>('DELETE', `/teacher/tests/${id}`),
  },

  tests: {
    list: () => request<StudentTest[]>('/tests'),
    get: (id: number) => request<StudentTest>(`/tests/${id}`),
    submit: (id: number, answers: string[]) => send<void>('POST', `/tests/${id}/submit`, { answers }),
  },

  admin: {
    summary: () => request<AdminSummary>('/admin/summary'),
    reports: () => request<ReportedWord[]>('/admin/reports'),
    dismiss: (wordId: number) => send<void>('POST', `/admin/reports/${wordId}/dismiss`),
    words: (query: string) => request<AdminWord[]>(`/admin/words?q=${encodeURIComponent(query)}`),
    save: (wordId: number, edit: WordEdit) => send<AdminWord>('PUT', `/admin/words/${wordId}`, edit),
  },
};
