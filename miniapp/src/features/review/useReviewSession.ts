import { useCallback, useEffect, useReducer } from 'react';

import { api } from '../../api/client';
import type { Rating } from '../../api/types';
import { impact, notify } from '../../lib/telegram';
import { initialState, reducer } from './session';

export function useReviewSession() {
  const [state, dispatch] = useReducer(reducer, initialState);

  const load = useCallback(async () => {
    dispatch({ type: 'loading' });
    try {
      const { cards } = await api.queue();
      dispatch({ type: 'loaded', cards });
    } catch (error) {
      dispatch({ type: 'failed', error: (error as Error).message });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const flip = useCallback(() => {
    impact('light');
    dispatch({ type: 'flip' });
  }, []);

  const rate = useCallback(
    (rating: Rating) => {
      const card = state.cards[state.index];
      if (!card) return;

      impact(rating === 1 ? 'heavy' : 'light');
      dispatch({ type: 'rate', rating });

      // Ответ уходит фоном, по одному. Восстанавливать порядок или
      // повторять запрос не пытаемся: потерянная оценка стоит одного
      // лишнего повторения, а очередь ретраев — целого слоя кода.
      api.review(card.id, rating).catch(() => {
        notify('error');
        dispatch({ type: 'syncError' });
      });
    },
    [state.cards, state.index],
  );

  return { state, flip, rate, reload: load } as const;
}
