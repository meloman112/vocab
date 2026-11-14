import type { QuizCard, Rating } from '../../api/types';
import { RIGHT, WRONG } from './check';

/** Ступеньки тренировки — режимы теста от узнавания к воспроизведению. */
export type Step = 'en-ru' | 'ru-en' | 'spell' | 'cloze';

export const LEARN_SIZE = 7;
/** Через сколько вопросов вернётся слово: сразу — это подглядывание, а не память. */
const COMEBACK = 2;
/** FSRS «выучено»: узнавание у слова уже есть. */
const REVIEW = 2;

export interface Item {
  card: QuizCard;
  steps: Step[];
  at: number;
  /** Худший ответ за тренировку — он и уйдёт в FSRS. */
  rating: Rating;
}

export function ladder(card: QuizCard): Step[] {
  const steps: Step[] = ['en-ru'];
  if (card.choices_en.length >= 2) steps.push('ru-en');
  steps.push('spell');
  if (card.cloze) steps.push('cloze');
  return steps;
}

/** Новое слово идёт с первой ступеньки, знакомое — сразу с «напиши сам». */
export function start(card: QuizCard): Item {
  const steps = ladder(card);
  return { card, steps, at: card.state === REVIEW ? steps.indexOf('spell') : 0, rating: RIGHT };
}

/**
 * Ответ на первое слово очереди. Верно — ступенькой выше, ошибка — ниже;
 * непройденное слово встаёт в очередь через COMEBACK вопросов.
 */
export function answer(queue: Item[], rating: Rating): { queue: Item[]; done: Item | null } {
  const [item, ...rest] = queue;
  if (!item) throw new Error('ответ без вопроса');
  const next: Item = {
    ...item,
    rating: Math.min(item.rating, rating) as Rating,
    at: rating === WRONG ? Math.max(0, item.at - 1) : item.at + 1,
  };
  if (next.at >= next.steps.length) return { queue: rest, done: next };
  rest.splice(Math.min(COMEBACK, rest.length), 0, next);
  return { queue: rest, done: null };
}

/** Доля пути: пройденные слова целиком, остальные — по своей ступеньке. */
export function progress(queue: Item[], words: number): number {
  const climbing = queue.reduce((sum, item) => sum + item.at / item.steps.length, 0);
  return (words - queue.length + climbing) / words;
}
