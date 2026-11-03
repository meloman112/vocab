import { api } from '../../api/client';
import type { ExerciseData, GrammarContent, PdfExercise, PdfPart, Rule, TopicData } from '../../api/types';
import { bracketLabel, isSlot, parseItem, type Part, type Slot } from './engine';

/**
 * Тетрадь целиком: темы, упражнения и задания по ключу «упражнение-индекс».
 * Задания разбираются движком лениво — при открытии, а не все 2300 разом.
 */
export interface Item {
  key: string;
  ex: number;
  /** Номер задания в книге, с единицы. */
  n: number;
  text: string;
}

export interface Exercise extends Omit<ExerciseData, 'items'> {
  topic: string;
  items: Item[];
}

export interface Book {
  rules: Record<string, Rule>;
  topics: TopicData[];
  exercises: Map<number, Exercise>;
  items: Map<string, Item>;
}

function build(content: GrammarContent): Book {
  const exercises = new Map<number, Exercise>();
  const items = new Map<string, Item>();
  for (const topic of content.topics) {
    for (const ex of topic.exercises) {
      const list = ex.items.map((text, i) => ({ key: `${ex.id}-${i}`, ex: ex.id, n: i + 1, text }));
      exercises.set(ex.id, { ...ex, topic: topic.id, items: list });
      for (const item of list) items.set(item.key, item);
    }
  }
  return { rules: content.rules, topics: content.topics, exercises, items };
}

let loading: Promise<Book> | null = null;

/** Один запрос на сессию: тетрадь нужна и ученику, и учителю. */
export function loadBook(): Promise<Book> {
  loading ??= api.grammar.content().then(build).catch((e: unknown) => {
    loading = null;
    throw e;
  });
  return loading;
}

const parsed = new Map<string, Part[]>();

export function partsOf(book: Book, key: string): Part[] {
  let parts = parsed.get(key);
  if (!parts) {
    const item = book.items.get(key)!;
    const ex = book.exercises.get(item.ex)!;
    parts = parseItem(item.text, ex.tenses, ex.choices ?? [], ex.commas ?? false);
    parsed.set(key, parts);
  }
  return parts;
}

export const slotsOf = (book: Book, key: string): Slot[] => partsOf(book, key).filter(isSlot);

/** Правило для подсказки: упражнения, разбора ошибки, времени пропуска, темы. */
export function ruleFor(book: Book, ex: Exercise, ...keys: (string | null | undefined)[]): Rule | undefined {
  const topic = book.topics.find((t) => t.id === ex.topic);
  for (const key of [ex.rule, ...keys, topic?.rules[0]]) if (key && book.rules[key]) return book.rules[key];
  return undefined;
}

/** Ответ с заглавной, если пропуск стоит в начале предложения. */
export function capitalizeAt(before: string, answer: string): string {
  if (!answer) return answer;
  return !before.trim() || /[.?!—\n]\s*$/.test(before) ? answer[0]!.toUpperCase() + answer.slice(1) : answer;
}

/** Предложение текстом с ответами (своими или из ключа) — для итогов и учителя. */
export function filled(book: Book, key: string, answers?: (string | null | undefined)[]): { text: string; answer?: boolean }[] {
  let j = 0;
  let before = '';
  return partsOf(book, key).map((p) => {
    if (typeof p === 'string') {
      before += p;
      return { text: p };
    }
    const value = capitalizeAt(before, answers?.[j] || p.ans[0]!);
    j++;
    before += value;
    return { text: value, answer: true };
  });
}

/** Упражнения для PDF: сделанное — с ответами, остальное — со скобками из книги. */
export function pdfExercises(book: Book, exIds: number[], results: Record<string, { answers: string[] }>): PdfExercise[] {
  return exIds.map((id) => {
    const ex = book.exercises.get(id)!;
    return {
      id,
      task: ex.task,
      items: ex.items.map((item) => {
        const r = results[item.key];
        let j = 0;
        let before = '';
        const parts: PdfPart[] = partsOf(book, item.key).map((p) => {
          if (typeof p === 'string') {
            before += p;
            return { text: p };
          }
          if (!r) return { hint: bracketLabel(p) || '___' };
          const answer = capitalizeAt(before, r.answers[j++] || p.ans[0]!);
          before += answer;
          return { answer };
        });
        return { n: item.n, done: !!r, parts };
      }),
    };
  });
}
