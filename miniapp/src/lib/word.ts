import type { Card } from '../api/types';

// «to book» и «a book» — разные карточки. На лицевой стороне без подсказки
// не понять, какую из них спрашивают. Артикль не ставим: «a water» хуже,
// чем подпись «существительное».
export const POS_HINTS: Record<string, string> = {
  noun: 'существительное',
  adjective: 'прилагательное',
  adverb: 'наречие',
};

export function title(card: Card): string {
  return card.homonym && card.pos === 'verb' ? `to ${card.word}` : card.word;
}

export const POS_NAMES: Record<string, string> = {
  ...POS_HINTS,
  verb: 'глагол',
  phrase: 'фраза',
};
