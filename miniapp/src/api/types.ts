export interface Card {
  id: number;
  word: string;
  status: string;
  translation: string | null;
  ipa: string | null;
  pos: string | null;
  example: string | null;
  example_ru: string | null;
  due: string;
}

/** 1 Again, 2 Hard, 3 Good, 4 Easy — нумерация py-fsrs, не своя. */
export type Rating = 1 | 2 | 3 | 4;

export interface ReviewResult {
  card_id: number;
  due: string;
  state: number;
}
