import type { Card, Rating } from '../../api/types';

/** empty — свои слова кончились; exhausted — и в общем словаре новых нет. */
export type Phase = 'loading' | 'error' | 'empty' | 'exhausted' | 'review' | 'done';

export interface SessionState {
  phase: Phase;
  cards: Card[];
  index: number;
  flipped: boolean;
  /** Сколько раз нажали Again — это и есть «сколько ошибок» в итоге. */
  lapses: number;
  /** Оценки, которые не доехали до сервера. Молча терять их нельзя. */
  syncErrors: number;
  error: string;
}

export type SessionAction =
  | { type: 'loading' }
  | { type: 'loaded'; cards: Card[]; whenEmpty: 'empty' | 'exhausted' }
  | { type: 'failed'; error: string }
  | { type: 'flip' }
  | { type: 'rate'; rating: Rating }
  | { type: 'syncError' };

export const initialState: SessionState = {
  phase: 'loading',
  cards: [],
  index: 0,
  flipped: false,
  lapses: 0,
  syncErrors: 0,
  error: '',
};

export function reducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case 'loading':
      return { ...initialState };

    case 'loaded':
      return {
        ...initialState,
        phase: action.cards.length === 0 ? action.whenEmpty : 'review',
        cards: action.cards,
      };

    case 'failed':
      return { ...state, phase: 'error', error: action.error };

    case 'flip':
      return { ...state, flipped: true };

    case 'rate': {
      const index = state.index + 1;
      return {
        ...state,
        // Карточка меняется сразу, не дожидаясь ответа сервера: пауза на
        // каждой оценке — единственное, что делает повторение утомительным.
        phase: index >= state.cards.length ? 'done' : 'review',
        index,
        flipped: false,
        lapses: state.lapses + (action.rating === 1 ? 1 : 0),
      };
    }

    case 'syncError':
      return { ...state, syncErrors: state.syncErrors + 1 };
  }
}
