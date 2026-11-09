import { Caption, LargeTitle, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useRef, useState } from 'react';

import type { QuizCard } from '../../../api/types';
import { celebrate } from '../../../lib/celebrate';
import { notify } from '../../../lib/telegram';
import { formOptions, RIGHT, WRONG } from '../check';
import { Feedback } from '../Feedback';
import type { Result } from '../useQuizSession';
import { ADVANCE_MS, optionClass } from './Choice';

const QUESTION = { v2: 'V2 — Past Simple', v3: 'V3 — Past Participle' };

/**
 * Первая ступень для свежего глагола: узнать форму среди похожих.
 * Выученный спрашивается вводом (Forms) — вспомнить труднее, чем узнать.
 */
export function FormChoice({ card, onDone }: { card: QuizCard; onDone: (results: Result[]) => void }) {
  const [ask] = useState<'v2' | 'v3'>(() => (Math.random() < 0.5 ? 'v2' : 'v3'));
  const [{ correct, options }] = useState(() => formOptions(card.word, card.forms, ask));
  const [picked, setPicked] = useState<string | null>(null);
  const timer = useRef<number>();

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const choose = (option: string, button: HTMLElement) => {
    if (picked !== null) return;
    setPicked(option);
    if (option !== correct) {
      notify('error');
      return;
    }
    notify('success');
    celebrate(button);
    timer.current = window.setTimeout(() => onDone([{ card, rating: RIGHT }]), ADVANCE_MS);
  };

  return (
    <>
      <div className="prompt">
        <LargeTitle weight="1" className="prompt__main">
          {card.word}
        </LargeTitle>
        <Caption className="hint">
          {card.translation} · {QUESTION[ask]}?
        </Caption>
      </div>

      <div className="options">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={optionClass(option, picked, correct)}
            disabled={picked !== null}
            onClick={(e) => choose(option, e.currentTarget)}
          >
            <Text>
              {picked !== null && option === correct && '✅ '}
              {option}
            </Text>
          </button>
        ))}
      </div>

      {picked !== null && picked !== correct && (
        <Feedback card={card} rating={WRONG} onNext={() => onDone([{ card, rating: WRONG }])} />
      )}
    </>
  );
}
