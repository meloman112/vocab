import type { DrillVerb, GrammarResult } from '../../api/types';
import { shuffle } from '../../lib/shuffle';
import type { Book, Exercise } from './book';
import { canInflect, STATE_VERBS, TENSES, type Person, type Tense } from './engine';

/** Тренировка форм: один глагол по лесенке известных времён, в трёх видах. */

// Порядок, в котором времена идут в тетради.
const ORDER: Tense[] = ['S', 'C', 'F', 'D', 'W', 'H', 'R', 'X'];
const MIN_DONE = 5;
const MIN_CLEAN = 0.7;
const CARDS = 10;
const CONTINUOUS = new Set<Tense>(['C', 'W', 'R']);

const MODES = [
  { label: 'утверждение', neg: false, question: false },
  { label: 'отрицание', neg: true, question: false },
  { label: 'вопрос', neg: false, question: true },
] as const;
const SUBJECTS: Record<Person, string[]> = { 1: ['I'], 3: ['he', 'she'], P: ['they', 'we', 'you'] };
const PERSONS = Object.keys(SUBJECTS) as Person[];

/** Время известно, когда по нему решено достаточно заданий и почти все чисто. */
export function knownTenses(book: Book, results: Record<string, GrammarResult>): Tense[] {
  return ORDER.filter((t) => {
    let done = 0, clean = 0;
    for (const ex of book.exercises.values()) {
      if (ex.tenses !== t) continue;
      for (const item of ex.items) {
        const r = results[item.key];
        if (!r) continue;
        done++;
        if (r.clean) clean++;
      }
    }
    return done >= MIN_DONE && clean / done >= MIN_CLEAN;
  });
}

/** Известные времена и первое неизвестное: растяжка без перегруза. */
export function ladder(known: Tense[]): Tense[] {
  const next = ORDER.find((t) => !known.includes(t));
  return next ? [...known, next] : known;
}

let counter = 0;

const pick = <T>(list: T[]): T => list[Math.floor(Math.random() * list.length)]!;

/** Упражнение из ~10 карточек: глагол за глаголом, у каждого — вся лесенка. */
export function buildDrill(book: Book, verbs: DrillVerb[], tenses: Tense[]): { book: Book; keys: string[] } {
  const id = 9000 + counter++;
  const usable = verbs.filter((v) => canInflect(v.lemma, v.irregular));
  const items: string[] = [];
  const chosen = shuffle(usable.slice(0, 15)).slice(0, Math.max(1, Math.ceil(CARDS / tenses.length)));
  chosen.forEach((verb, vi) => {
    const person = pick(PERSONS);
    const subject = pick(SUBJECTS[person]);
    tenses.forEach((t, ti) => {
      if (CONTINUOUS.has(t) && STATE_VERBS.has(verb.lemma)) return;
      const mode = MODES[(vi + ti) % MODES.length]!;
      const gap = `${mode.neg ? 'not ' : ''}to ${verb.lemma}`;
      const code = `${t}${person}`;
      items.push(
        `${TENSES[t].name}, ${mode.label}: ` +
        (mode.question ? `{${subject}|${gap}|${code}}` : `${subject} {|${gap}|${code}}`),
      );
    });
  });
  const ex: Exercise = {
    id, tenses: tenses.join(''), topic: '', task: 'Поставьте глагол в указанное время и вид.',
    items: items.map((text, i) => ({ key: `${id}-${i}`, ex: id, n: i + 1, text })),
  };
  const copy: Book = { ...book, exercises: new Map(book.exercises).set(id, ex), items: new Map(book.items) };
  for (const item of ex.items) copy.items.set(item.key, item);
  return { book: copy, keys: ex.items.map((i) => i.key) };
}
