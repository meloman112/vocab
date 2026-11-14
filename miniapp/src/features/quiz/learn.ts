import type { QuizCard, Rating } from '../../api/types';
import { distance, RIGHT, WRONG } from './check';

/** Ступеньки тренировки — режимы теста от узнавания к воспроизведению. */
export type Step = 'en-ru' | 'ru-en' | 'spell' | 'cloze' | 'contrast';

export const LEARN_SIZE = 7;
/** Через сколько вопросов вернётся слово: после ошибки — скоро, после верного — позже. */
const AFTER_WRONG = 1;
const AFTER_RIGHT = 3;
/** FSRS «выучено»: узнавание у слова уже есть. */
const REVIEW = 2;

export interface Item {
  card: QuizCard;
  steps: Step[];
  at: number;
  /** Ни одной ошибки за тренировку: такое слово идёт коротким путём. */
  clean: boolean;
  /** Худший ответ за тренировку — он и уйдёт в FSRS. */
  rating: Rating;
}

export function ladder(card: QuizCard): Step[] {
  const steps: Step[] = ['en-ru'];
  if (card.choices_en.length >= 2) steps.push('ru-en');
  steps.push('spell');
  if (card.cloze) steps.push('cloze');
  // Похожие слова — только выученному: на первом знакомстве они мешают запомнить.
  if (card.state === REVIEW && card.contrast?.quiz) steps.push('contrast');
  return steps;
}

/** Новое слово идёт с первой ступеньки, знакомое — сразу с «напиши сам». */
export function start(card: QuizCard): Item {
  const steps = ladder(card);
  return { card, steps, at: card.state === REVIEW ? steps.indexOf('spell') : 0, clean: true, rating: RIGHT };
}

/** «носить (одежду), нести» → {носить, нести}: пояснение в скобках не значение. */
function meanings(translation: string): Set<string> {
  return new Set(
    translation.replace(/\(.*?\)/g, '').split(/[,;]/).map((m) => m.trim().toLowerCase()).filter(Boolean),
  );
}

/**
 * Слова, которые рядом путаются: одно слово (bad — плохой / плохо, grow — grow up),
 * общее значение (rise и grow — «расти»), похожее написание (beat, bear, wear).
 */
export function confusable(a: QuizCard, b: QuizCard): boolean {
  if (a.word.split(' ')[0] === b.word.split(' ')[0]) return true;
  const shared = meanings(b.translation);
  if ([...meanings(a.translation)].some((m) => shared.has(m))) return true;
  return Math.min(a.word.length, b.word.length) >= 3 && distance(a.word, b.word) <= 2;
}

/** Порядок без путаницы по соседству — насколько получится. */
export function spread(items: Item[]): Item[] {
  const rest = [...items];
  const out: Item[] = [];
  while (rest.length) {
    const last = out[out.length - 1];
    const index = Math.max(0, rest.findIndex((i) => !last || !confusable(i.card, last.card)));
    out.push(...rest.splice(index, 1));
  }
  return out;
}

/** Ставит слово не раньше чем через gap вопросов и не рядом с тем, с чем оно путается. */
function putBack(queue: Item[], item: Item, gap: number): Item[] {
  const fits = (i: number) =>
    [queue[i - 1], queue[i]].every((n) => !n || !confusable(n.card, item.card));
  let at = Math.min(gap, queue.length);
  while (at <= queue.length && !fits(at)) at++;
  const index = at > queue.length ? Math.min(gap, queue.length) : at;
  return [...queue.slice(0, index), item, ...queue.slice(index)];
}

/**
 * Ответ на первое слово очереди. Верно с первого раза — прыжок: с выбора сразу
 * на «напиши», с «напиши» — на «различай» или готово. После ошибки — вся лесенка
 * и возврат скорее.
 */
export function answer(queue: Item[], rating: Rating): { queue: Item[]; done: Item | null } {
  const [item, ...rest] = queue;
  if (!item) throw new Error('ответ без вопроса');
  const wrong = rating === WRONG;
  // Подсказка или опечатка — уже не «с первого раза».
  const clean = item.clean && rating === RIGHT;
  let at = wrong ? Math.max(0, item.at - 1) : item.at + 1;
  if (clean) {
    const jumps = [item.steps.indexOf('spell'), item.steps.indexOf('contrast'), item.steps.length];
    at = Math.min(...jumps.filter((i) => i > item.at));
  }
  const next: Item = { ...item, at, clean, rating: Math.min(item.rating, rating) as Rating };
  if (next.at >= next.steps.length) return { queue: rest, done: next };
  return { queue: putBack(rest, next, wrong ? AFTER_WRONG : AFTER_RIGHT), done: null };
}

/** Доля пути: пройденные слова целиком, остальные — по своей ступеньке. */
export function progress(queue: Item[], words: number): number {
  const climbing = queue.reduce((sum, item) => sum + item.at / item.steps.length, 0);
  return (words - queue.length + climbing) / words;
}

/** ●●○○ — где слово на лесенке. */
export function dots(item: Item): string {
  return item.steps.map((_, i) => (i < item.at ? '●' : '○')).join('');
}
