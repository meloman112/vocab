export interface Example {
  en: string;
  ru: string;
}

export interface Card {
  id: number;
  word: string;
  translation: string;
  ipa: string;
  pos: string;
  /** go · went · gone; пустая строка, если формы правильные. */
  forms: string;
  irregular: boolean;
  examples: Example[];
  /** «топ-500» — место по частоте в языке. */
  top: string;
  /** Сколько человек учат слово. */
  learners: number;
  /** У леммы есть другие части речи (a book / to book). */
  homonym: boolean;
  due: string;
}

/** Как XP_PER_REVIEW в backend/repo.py: XP — это число повторений × 10. */
export const XP_PER_REVIEW = 10;

export interface Stats {
  due_now: number;
  /** Дней подряд с повторением; пропущенный день — уже 0. */
  streak: number;
  best_streak: number;
}

export interface LeaderRow {
  place: number;
  name: string;
  xp: number;
  streak: number;
}

/** Рейтинг недели: XP с понедельника. me — своё место, даже ниже топа. */
export interface Leaderboard {
  top: LeaderRow[];
  me: LeaderRow | null;
}

/** 1 Again, 2 Hard, 3 Good, 4 Easy — нумерация py-fsrs, не своя. */
export type Rating = 1 | 2 | 3 | 4;

export interface ReviewResult {
  card_id: number;
  due: string;
  state: number;
}
