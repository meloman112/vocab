import type { DrillVerb, GrammarResult } from '../../api/types';
import { shuffle } from '../../lib/shuffle';
import { slotsOf, type Book } from './book';
import { canInflect, diagnose, parseSlot, STATE_VERBS, type Diagnosis, type Person, type Slot, type Tense } from './engine';

/** Тренировка форм: один глагол и одно лицо, в каждом известном времени — «+», «−», «?». */

// Порядок, в котором времена идут в тетради.
const ORDER: Tense[] = ['S', 'C', 'F', 'D', 'W', 'H', 'R', 'X'];
const MIN_DONE = 5;
const MIN_CLEAN = 0.7;
const CONTINUOUS = new Set<Tense>(['C', 'W', 'R']);

/** Лица идут по кругу от таблицы к таблице: иначе -s и does не тренируются. */
export const PEOPLE: { subject: string; person: Person }[] = [
  { subject: 'I', person: '1' }, { subject: 'he', person: '3' }, { subject: 'they', person: 'P' },
  { subject: 'she', person: '3' }, { subject: 'we', person: 'P' }, { subject: 'you', person: 'P' },
];

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


/** Время с наибольшей долей заданий с ошибкой; без данных или без ошибок — null. */
export function weakTense(book: Book, results: Record<string, GrammarResult>, tenses: Tense[]): Tense | null {
  let weak: Tense | null = null, worst = 0;
  for (const t of tenses) {
    let done = 0, wrong = 0;
    for (const key of book.items.keys()) {
      const r = results[key];
      if (!r || !slotsOf(book, key).some((s) => s.tense === t)) continue;
      done++;
      if (!r.clean) wrong++;
    }
    if (done < MIN_DONE || wrong / done <= worst) continue;
    weak = t;
    worst = wrong / done;
  }
  return weak;
}

/** Времена таблицы: слабое первым, после чистой таблицы — вперемешку; state verbs без Continuous. */
export function drillTenses(tenses: Tense[], verb: string, weak: Tense | null, random: boolean): Tense[] {
  const usable = tenses.filter((t) => !(CONTINUOUS.has(t) && STATE_VERBS.has(verb)));
  if (random) return shuffle(usable);
  return weak && usable.includes(weak) ? [weak, ...usable.filter((t) => t !== weak)] : usable;
}

/** Случайный глагол, который движок умеет спрягать, не тот же, что в прошлой таблице. */
export function pickVerb(verbs: DrillVerb[], previous: string | null): string | null {
  const usable = verbs.filter((v) => canInflect(v.lemma, v.irregular));
  const fresh = usable.length > 1 ? usable.filter((v) => v.lemma !== previous) : usable;
  return fresh.length ? fresh[Math.floor(Math.random() * fresh.length)]!.lemma : null;
}

export interface DrillRow {
  sign: '+' | '−' | '?';
  subject: string;
  slot: Slot;
  /** Эталон целиком, как его пишет ученик. */
  answer: string;
}

const upper = (s: string) => s[0]!.toUpperCase() + s.slice(1);

/** Три строки времени: утверждение, отрицание, вопрос. */
export function drillRows(verb: string, subject: string, person: Person, tense: Tense): DrillRow[] {
  const slot = (lead: string, neg: boolean) =>
    parseSlot(lead, `${neg ? 'not ' : ''}to ${verb}`, `${tense}${person}`, '', '', tense, [], false);
  const statement = (sign: '+' | '−', neg: boolean): DrillRow => {
    const s = slot('', neg);
    return { sign, subject, slot: s, answer: `${subject} ${s.ans[0]}` };
  };
  const question = slot(subject, false);
  return [
    statement('+', false), statement('−', true),
    { sign: '?', subject, slot: question, answer: `${upper(question.ans[0]!)}?` },
  ];
}

/** Разбор поля. Подлежащее в «+» и «−» снимаем сами: движок знает только глагольную часть. */
export function checkRow(row: DrillRow, input: string): Diagnosis {
  const text = input.trim();
  if (row.sign === '?' || !text) return diagnose(text, row.slot);
  const rest = text.replace(new RegExp(`^${row.subject}\\b`, 'i'), '');
  if (rest === text) return { why: `Напиши с подлежащим: ${row.subject} …`, more: 'Подлежащее в начале, потом глагол.' };
  // «I'm» остаётся «'m»: норма знает только целое «i'm».
  return diagnose(rest.replace(/^['’]m\b/i, 'am').trim(), row.slot);
}
