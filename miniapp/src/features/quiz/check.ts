import type { Card, Rating } from '../../api/types';
import { shuffle } from '../../lib/shuffle';
import { irregularForms } from '../../lib/word';

/**
 * Оценка FSRS из ответа: тест ставит её сам, вместо кнопок Again…Easy.
 * Easy тест не ставит никогда: верный ответ ещё не значит «слишком легко».
 */
export const RIGHT: Rating = 3;
export const ALMOST: Rating = 2;
export const WRONG: Rating = 1;

export function normalize(text: string): string {
  return text.trim().toLowerCase().replace(/[’`]/g, "'").replace(/\s+/g, ' ');
}

/** Расстояние Левенштейна: сколько правок отделяет ответ от правильного. */
export function distance(a: string, b: string): number {
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const current = [i];
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      current.push(Math.min(previous[j]! + 1, current[j - 1]! + 1, previous[j - 1]! + cost));
    }
    previous = current;
  }
  return previous[b.length]!;
}

/** Хотя бы один правильный ответ есть всегда: первый показывается как «правильно». */
export type Answers = [string, ...string[]];

export interface Grade {
  rating: Rating;
  /** Почему не RIGHT: «опечатка», «нужна форма went». */
  note?: string;
}

/**
 * Введённое слово против правильных вариантов. Одна опечатка в слове
 * от 4 букв — ALMOST: слово вспомнил, а правописание FSRS не учит.
 * near — ответы «почти»: лемма вместо нужной формы (go вместо went).
 */
export function grade(input: string, accepted: Answers, near: string[] = []): Grade {
  const answer = normalize(input);
  const targets = accepted.map(normalize);
  if (targets.includes(answer)) return { rating: RIGHT };
  if (answer.length >= 4 && targets.some((t) => distance(answer, t) <= 1)) {
    return { rating: ALMOST, note: 'опечатка' };
  }
  if (near.map(normalize).includes(answer)) {
    return { rating: ALMOST, note: `нужна форма «${accepted[0]}»` };
  }
  return { rating: WRONG };
}

/** «to book» и «book» — оба верный ответ для глагола. */
export function acceptedWords(card: Card): Answers {
  return card.pos === 'verb' ? [card.word, `to ${card.word}`] : [card.word];
}

/** «h _ _ _» — подсказка: первая буква и длина. */
export function hint(word: string): string {
  return [...word].map((char, i) => (i === 0 || char === ' ' ? char : '_')).join(' ');
}

/** Типичные ошибки — неверные варианты: правильное -ed (singed) и соседняя форма. */
function regular(verb: string): string {
  return verb.endsWith('e') ? `${verb}d` : `${verb}ed`;
}

/** sing, V2 → sang среди sung, sing, singed. */
export function formOptions(lemma: string, forms: string, ask: 'v2' | 'v3'): { correct: string; options: string[] } {
  const all = irregularForms(forms);
  const right = all[ask];
  const correct = right[0]!;
  const other = ask === 'v2' ? all.v3 : all.v2;
  const wrong = [...other, lemma, regular(lemma), regular(correct)].filter((option) => !right.includes(option));
  return { correct, options: shuffle([correct, ...[...new Set(wrong)].slice(0, 3)]) };
}
