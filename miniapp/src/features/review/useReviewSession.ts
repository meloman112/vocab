import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { api } from '../../api/client';
import type { Card, Rating } from '../../api/types';
import { impact, notify } from '../../lib/telegram';
import { initialState, reducer } from './session';

/** С deck сессия сразу берёт новые слова этого набора, а не очередь повторения. */
export function useReviewSession(deck?: string) {
  const [state, dispatch] = useReducer(reducer, initialState);
  // Последняя карточка, отмеченная «Знаю», пока висит предложение отменить.
  const [known, setKnown] = useState<Card | null>(null);
  // Оценки уходят фоном; итог сессии ждёт их, иначе серия и XP на экране
  // «Готово» отставали бы на последнюю карточку.
  const pending = useRef<Promise<unknown>[]>([]);

  const fetchCards = useCallback(
    async (source: () => ReturnType<typeof api.queue>, whenEmpty: 'empty' | 'exhausted') => {
      dispatch({ type: 'loading' });
      try {
        const { cards, new_left } = await source();
        dispatch({ type: 'loaded', cards, whenEmpty: new_left === 0 ? 'enough' : whenEmpty });
      } catch (error) {
        dispatch({ type: 'failed', error: (error as Error).message });
      }
    },
    [],
  );

  const learnNew = useCallback(() => fetchCards(() => api.discover(deck), 'exhausted'), [fetchCards, deck]);
  const load = useCallback(
    () => (deck ? learnNew() : fetchCards(api.queue, 'empty')),
    [deck, learnNew, fetchCards],
  );

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
      const sent = api.review(card.id, rating, 'card').catch(() => {
        notify('error');
        dispatch({ type: 'syncError' });
      });
      pending.current.push(sent);
    },
    [state.cards, state.index],
  );

  const markKnown = useCallback(() => {
    const card = state.cards[state.index];
    if (!card) return;

    impact('light');
    dispatch({ type: 'known' });
    setKnown(card);
    pending.current.push(api.known(card.id).catch(() => {
      notify('error');
      dispatch({ type: 'syncError' });
    }));
  }, [state.cards, state.index]);

  // Отмена только снимает отметку: в эту сессию карточка не вернётся, но
  // её расписание не трогали, и она придёт в свой срок.
  const undoKnown = useCallback(() => {
    if (!known) return;
    setKnown(null);
    pending.current.push(api.unknown(known.id).catch(() => {
      notify('error');
      dispatch({ type: 'syncError' });
    }));
  }, [known]);

  const settled = useCallback(() => Promise.all(pending.current), []);

  return {
    state, flip, rate, markKnown, known, undoKnown, dismissKnown: () => setKnown(null),
    reload: load, learnNew, settled,
  } as const;
}
