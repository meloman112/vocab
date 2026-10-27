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
  due: string;
}

/** 1 Again, 2 Hard, 3 Good, 4 Easy — нумерация py-fsrs, не своя. */
export type Rating = 1 | 2 | 3 | 4;

export interface ReviewResult {
  card_id: number;
  due: string;
  state: number;
}
