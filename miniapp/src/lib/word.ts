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

/** «go · went · gone» → варианты V2 и V3; «learned/learnt» — оба верны. */
export function irregularForms(forms: string): { v2: string[]; v3: string[] } {
  const [, v2 = '', v3 = ''] = forms.split('·').map((part) => part.trim());
  const variants = (part: string) => part.split('/').map((v) => v.trim()).filter(Boolean);
  return { v2: variants(v2), v3: variants(v3) };
}

/**
 * Образец форм: 170 глаголов по одному не запомнить, а четыре образца —
 * легко, и новый глагол сразу ложится в знакомую группу.
 */
export function irregularPattern(forms: string): string | null {
  const [v1] = forms.split('·').map((part) => part.trim());
  const { v2, v3 } = irregularForms(forms);
  const [past, participle] = [v2[0], v3[0]];
  if (!v1 || !past || !participle) return null;
  if (v1 === past && past === participle) return 'A-A-A: все формы одинаковые, как cut · cut · cut';
  if (past === participle) return 'A-B-B: V2 = V3, как buy · bought · bought';
  if (v1 === participle) return 'A-B-A: V3 = V1, как come · came · come';
  return 'A-B-C: все три разные, как go · went · gone';
}
