import { Caption, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useMemo, useRef, useState } from 'react';

import type { QuizCard } from '../../../api/types';
import { celebrate } from '../../../lib/celebrate';
import { impact, notify } from '../../../lib/telegram';
import { title } from '../../../lib/word';
import { RIGHT, WRONG } from '../check';
import type { Result } from '../useQuizSession';

const FLASH_MS = 500;

function shuffled<T>(items: T[]): T[] {
  return items
    .map((item) => ({ item, key: Math.random() }))
    .sort((a, b) => a.key - b.key)
    .map(({ item }) => item);
}

/**
 * Слева слова, справа переводы. Промах засчитывается слову, которое
 * выбрано слева: именно его перевод не вспомнился.
 */
export function Pairs({ round, onDone }: { round: QuizCard[]; onDone: (results: Result[]) => void }) {
  const right = useMemo(() => shuffled(round), [round]);
  const [selected, setSelected] = useState<number | null>(null);
  const [matched, setMatched] = useState<Set<number>>(new Set());
  const [missed, setMissed] = useState<Set<number>>(new Set());
  const [wrong, setWrong] = useState<number | null>(null);
  const timer = useRef<number>();

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const pickTranslation = (cardId: number) => {
    if (selected === null || matched.has(cardId)) return;
    if (cardId !== selected) {
      notify('error');
      setMissed((m) => new Set(m).add(selected));
      setWrong(cardId);
      timer.current = window.setTimeout(() => setWrong(null), FLASH_MS);
      return;
    }
    impact('light');
    const next = new Set(matched).add(cardId);
    setMatched(next);
    setSelected(null);
    if (next.size === round.length) {
      notify('success');
      // Салют — за раунд без промахов, иначе он ничего не значит.
      if (missed.size === 0) celebrate();
      const results = round.map((card) => ({ card, rating: missed.has(card.id) ? WRONG : RIGHT }));
      timer.current = window.setTimeout(() => onDone(results), FLASH_MS);
    }
  };

  return (
    <>
      <Caption className="hint prompt">Выбери слово, потом его перевод</Caption>
      <div className="pairs">
        <div className="pairs__col">
          {round.map((card) => (
            <button
              key={card.id}
              type="button"
              className={tileClass(matched.has(card.id), selected === card.id, false)}
              disabled={matched.has(card.id)}
              onClick={() => setSelected(card.id)}
            >
              <Text weight="2">{title(card)}</Text>
            </button>
          ))}
        </div>
        <div className="pairs__col">
          {right.map((card) => (
            <button
              key={card.id}
              type="button"
              className={tileClass(matched.has(card.id), false, wrong === card.id)}
              disabled={matched.has(card.id)}
              onClick={() => pickTranslation(card.id)}
            >
              <Text>{card.translation}</Text>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

function tileClass(done: boolean, active: boolean, wrong: boolean): string {
  if (done) return 'option option--right option--dim';
  if (wrong) return 'option option--wrong';
  if (active) return 'option option--active';
  return 'option';
}
