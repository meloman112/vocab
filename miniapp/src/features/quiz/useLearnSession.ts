import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../../api/client';
import { notify } from '../../lib/telegram';
import { WRONG } from './check';
import { answer, dots, type Item, LEARN_SIZE, progress, spread, start } from './learn';
import type { Result } from './useQuizSession';

type Phase = 'loading' | 'error' | 'empty' | 'play' | 'done';

/** Тренировка: очередь слов по лесенке; в FSRS — одна оценка за пройденное слово. */
export function useLearnSession() {
  const [phase, setPhase] = useState<Phase>('loading');
  const [error, setError] = useState('');
  const [queue, setQueue] = useState<Item[]>([]);
  const [words, setWords] = useState(0);
  const [turn, setTurn] = useState(0);
  const [lapses, setLapses] = useState(0);
  const [syncErrors, setSyncErrors] = useState(0);
  const pending = useRef<Promise<unknown>[]>([]);

  const load = useCallback(async () => {
    setPhase('loading');
    setTurn(0);
    setLapses(0);
    setSyncErrors(0);
    pending.current = [];
    try {
      const { cards } = await api.quiz('learn', LEARN_SIZE);
      const items = spread(cards.filter((card) => card.choices_ru.length >= 2).map(start));
      setQueue(items);
      setWords(items.length);
      setPhase(items.length === 0 ? 'empty' : 'play');
    } catch (e) {
      setError((e as Error).message);
      setPhase('error');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const finish = useCallback(
    ([result]: Result[]) => {
      if (!result) throw new Error('упражнение не вернуло ответ');
      const { queue: next, done } = answer(queue, result.rating);
      if (done) {
        const sent = api.review(done.card.id, done.rating, 'learn').catch(() => {
          notify('error');
          setSyncErrors((n) => n + 1);
        });
        pending.current.push(sent);
        if (done.rating === WRONG) setLapses((n) => n + 1);
      }
      setQueue(next);
      setTurn((n) => n + 1);
      if (next.length === 0) setPhase('done');
    },
    [queue],
  );

  const settled = useCallback(() => Promise.all(pending.current), []);
  const current = queue[0];

  return {
    phase,
    error,
    round: current ? [current.card] : [],
    step: current ? current.steps[current.at]! : null,
    turn,
    progress: words ? progress(queue, words) : 0,
    counter: `${words - queue.length}/${words} слов${current ? ` · ${dots(current)}` : ''}`,
    answered: words,
    lapses,
    syncErrors,
    finish,
    settled,
    reload: load,
  } as const;
}
