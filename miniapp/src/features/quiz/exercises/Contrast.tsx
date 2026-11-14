import { Caption, LargeTitle, Text } from '@telegram-apps/telegram-ui';
import { useMemo, useState } from 'react';

import type { QuizCard } from '../../../api/types';
import { celebrate } from '../../../lib/celebrate';
import { shuffle } from '../../../lib/shuffle';
import { notify } from '../../../lib/telegram';
import { RIGHT, WRONG } from '../check';
import { Feedback } from '../Feedback';
import type { Result } from '../useQuizSession';
import { optionClass } from './Choice';

interface Props {
  card: QuizCard;
  onDone: (results: Result[]) => void;
}

/** «Различай»: предложение с пропуском, варианты — слова, с которыми путают. После ответа — правило. */
export function Contrast({ card, onDone }: Props) {
  const contrast = card.contrast;
  const quiz = contrast?.quiz;
  if (!contrast || !quiz) throw new Error(`у ${card.word} нет теста на различие`);
  const correct = quiz.options[0]!;
  const options = useMemo(() => shuffle(quiz.options), [quiz]);
  const [picked, setPicked] = useState<string | null>(null);
  const rating = picked === null ? null : picked === correct ? RIGHT : WRONG;

  const choose = (option: string, button: HTMLElement) => {
    if (picked !== null) return;
    setPicked(option);
    notify(option === correct ? 'success' : 'error');
    if (option === correct) celebrate(button);
  };

  return (
    <>
      <div className="prompt">
        <Caption className="hint">⚖️ Что подходит?</Caption>
        <LargeTitle weight="1" className="prompt__main prompt__main--text">
          {quiz.text}
        </LargeTitle>
        {picked !== null && <Caption className="hint">{quiz.ru}</Caption>}
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
            <Text>{option}</Text>
          </button>
        ))}
      </div>

      {rating !== null && (
        <>
          <div className="feedback">
            <Text>
              <b>{card.word}</b> — {contrast.note}
            </Text>
            {contrast.others.map((other) => (
              <Text key={other.word}>
                <b>{other.word}</b> — {other.note}
              </Text>
            ))}
          </div>
          <Feedback card={card} rating={rating} onNext={() => onDone([{ card, rating }])} />
        </>
      )}
    </>
  );
}
