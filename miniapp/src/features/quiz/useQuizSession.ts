import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../../api/client';
import type { QuizCard, Rating } from '../../api/types';
import { notify } from '../../lib/telegram';
import { ALMOST, WRONG } from './check';
import type { Mode } from './modes';

export const QUIZ_SIZE = 10;
const PAIRS_ROUND = 5;

export interface Result {
  card: QuizCard;
  rating: Rating;
}

type Phase = 'loading' | 'error' | 'empty' | 'play' | 'done';

/**
 * Раунд — то, что видно на одном экране: одна карточка, а в «Парах» пять.
 * Хвост короче двух пар не отдельный раунд — одна пара не тест.
 */
function rounds(cards: QuizCard[], pairs: boolean): QuizCard[][] {
  if (!pairs) return cards.map((card) => [card]);
  const result: QuizCard[][] = [];
  for (let i = 0; i < cards.length; i += PAIRS_ROUND) {
    const chunk = cards.slice(i, i + PAIRS_ROUND);
    const previous = result[result.length - 1];
    if (chunk.length < 2 && previous) previous.push(...chunk);
    else result.push(chunk);
  }
  return result;
}

export function useQuizSession(mode: Mode) {
  const [phase, setPhase] = useState<Phase>('loading');
  const [error, setError] = useState('');
  const [items, setItems] = useState<QuizCard[][]>([]);
  const [index, setIndex] = useState(0);
  const [answered, setAnswered] = useState(0);
  const [lapses, setLapses] = useState(0);
  const [syncErrors, setSyncErrors] = useState(0);
  // Как в повторении: оценки уходят фоном, итог ждёт их всех.
  const pending = useRef<Promise<unknown>[]>([]);

  const load = useCallback(async () => {
    setPhase('loading');
    setIndex(0);
    setAnswered(0);
    setLapses(0);
    setSyncErrors(0);
    pending.current = [];
    try {
      const { cards } = await api.quiz(mode.source, QUIZ_SIZE);
      const fitting = cards.filter(mode.fits);
      setItems(rounds(fitting, mode.id === 'pairs'));
      setPhase(fitting.length === 0 ? 'empty' : 'play');
    } catch (e) {
      setError((e as Error).message);
      setPhase('error');
    }
  }, [mode]);

  useEffect(() => {
    void load();
  }, [load]);

  const finish = useCallback(
    (results: Result[]) => {
      for (const { card, rating } of results) {
        // Угадать из четырёх — не вспомнить: такое «верно» для FSRS только Hard,
        // иначе слово уходит надолго и забывается до следующей встречи.
        const sent = api.review(card.id, mode.recall ? rating : (Math.min(rating, ALMOST) as Rating), mode.id).catch(() => {
          notify('error');
          setSyncErrors((n) => n + 1);
        });
        pending.current.push(sent);
      }
      setAnswered((n) => n + results.length);
      setLapses((n) => n + results.filter((r) => r.rating === WRONG).length);
      const next = index + 1;
      setIndex(next);
      if (next >= items.length) setPhase('done');
    },
    [index, items.length, mode],
  );

  const settled = useCallback(() => Promise.all(pending.current), []);

  return {
    phase,
    error,
    round: items[index] ?? [],
    step: null,
    turn: index,
    progress: items.length ? index / items.length : 0,
    counter: `${index + 1}/${items.length}`,
    answered,
    lapses,
    syncErrors,
    finish,
    settled,
    reload: load,
  } as const;
}
