export interface Example {
  en: string;
  ru: string;
}

export interface Card {
  id: number;
  /** Слово общего словаря: жалоба идёт на него, а не на карточку. */
  word_id: number;
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

/** Перевод выделенного слова. saved — уже есть в карточках. */
export interface Lookup {
  id: number;
  lemma: string;
  /** «went — прошедшее время», если выделили не лемму. */
  form_note: string | null;
  translation: string;
  ipa: string;
  pos: string;
  forms: string;
  examples: Example[];
  saved: boolean;
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

export interface Cloze {
  /** «She _____ home.» */
  text: string;
  /** Форма из предложения (went), а не лемма. */
  answer: string;
  ru: string;
}

/** Карточка для теста: варианты собирает сервер, правильный среди них. */
export interface QuizCard extends Card {
  choices_ru: string[];
  choices_en: string[];
  cloze: Cloze | null;
}

/** Откуда сервер берёт карточки теста. */
export type QuizSource = 'any' | 'irregular' | 'cloze';

export type ReportReason = 'typo' | 'translation' | 'example' | 'other';

export const REPORT_REASONS: Record<ReportReason, string> = {
  typo: 'Опечатка, нет такого слова',
  translation: 'Неверный перевод',
  example: 'Плохой пример',
  other: 'Другое',
};

export interface Me {
  is_admin: boolean;
  is_teacher: boolean;
  grammar_done: number;
  grammar_wrong: number;
}

// --- тетрадь ---------------------------------------------------------------

export interface Rule {
  title: string;
  formula: string;
  text: string;
}

export interface ExerciseData {
  id: number;
  /** Времена упражнения кодами движка: «CS», «DWX». Пусто — ручные ответы. */
  tenses: string;
  task: string;
  items: string[];
  /** Правило, которое открывает подсказка, — если не по времени пропуска. */
  rule?: string;
  /** Варианты для плиток: who / which / that… */
  choices?: string[];
  /** Запятые проверяются (non-defining clauses). */
  commas?: boolean;
}

export interface TopicData {
  id: string;
  title: string;
  rules: string[];
  exercises: ExerciseData[];
}

export interface GrammarContent {
  rules: Record<string, Rule>;
  topics: TopicData[];
}

export interface GrammarResult {
  clean: boolean;
  was_wrong: boolean;
  answers: string[];
}

export interface GrammarProgress {
  results: Record<string, GrammarResult>;
  /** Засчитанные учителем ответы: item → номер пропуска → ответы. */
  accepted: Record<string, Record<string, string[]>>;
}

export interface GrammarMistakeIn {
  slot: number;
  answer: string;
  why: string;
}

export interface GrammarAttempt {
  item: string;
  clean: boolean;
  answers: string[];
  mistakes: GrammarMistakeIn[];
}

/** Предложение для PDF: текст книги, ответ ученика или скобки несделанного. */
export interface PdfPart {
  text?: string;
  answer?: string;
  hint?: string;
}

export interface PdfExercise {
  id: number;
  task: string;
  items: { n: number; done: boolean; parts: PdfPart[] }[];
}

export interface Student {
  user_id: number;
  name: string;
  done: number;
  first_try: number;
  wrong_now: number;
  /** Неразобранные ошибки — учитель их ещё не засчитал. */
  mistakes: number;
  mistakes_week: number;
  last_at: string | null;
}

export interface StudentResult {
  item: string;
  clean: boolean;
  was_wrong: boolean;
  answers: (string | null)[];
  updated_at: string;
}

export interface StudentMistake {
  id: number;
  item: string;
  slot: number;
  answer: string;
  why: string;
  created_at: string;
  accepted: boolean;
}

export interface StudentDetail {
  user_id: number;
  name: string;
  results: StudentResult[];
  mistakes: StudentMistake[];
}

export interface CommonMistake {
  item: string;
  students: number;
  attempts: number;
  answers: string[];
}

export type Level = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';

export interface AdminWord {
  id: number;
  lemma: string;
  translation: string;
  ipa: string;
  pos: string;
  forms: string;
  irregular: boolean;
  examples: Example[];
  level: Level | null;
  banned: boolean;
}

export interface ReportedWord extends AdminWord {
  reports: number;
  reasons: ReportReason[];
  comments: string[];
  last_at: string;
}

/** Что админ может поменять: лемма и часть речи — ключ слова. */
export type WordEdit = Omit<AdminWord, 'id' | 'lemma' | 'pos'>;

export interface AdminSummary {
  users: number;
  active_week: number;
  words: number;
  banned: number;
  open_reports: number;
}
