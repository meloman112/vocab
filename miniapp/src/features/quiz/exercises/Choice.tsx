import { Button, Caption, LargeTitle, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useRef, useState } from 'react';

import type { QuizCard, Rating } from '../../../api/types';
import { speak } from '../../../lib/speech';
import { notify } from '../../../lib/telegram';
import { POS_HINTS, title } from '../../../lib/word';
import { ALMOST, RIGHT, WRONG } from '../check';
import { Feedback } from '../Feedback';
import type { Result } from '../useQuizSession';

/** Сколько видна зелёная подсветка верного ответа перед следующим вопросом. */
const ADVANCE_MS = 700;

interface Props {
  card: QuizCard;
  /** en-ru и listen: переводы; ru-en: слова. */
  direction: 'en-ru' | 'ru-en';
  listen?: boolean;
  onDone: (results: Result[]) => void;
}

export function Choice({ card, direction, listen = false, onDone }: Props) {
  const [picked, setPicked] = useState<string | null>(null);
  const [rating, setRating] = useState<Rating | null>(null);
  // В «На слух» слово можно подсмотреть — тогда это уже не проверка слуха.
  const [revealed, setRevealed] = useState(!listen);
  const timer = useRef<number>();

  const options = direction === 'en-ru' ? card.choices_ru : card.choices_en;
  const correct = direction === 'en-ru' ? card.translation : card.word;

  useEffect(() => {
    if (listen) speak(card.word);
    return () => window.clearTimeout(timer.current);
  }, [card.word, listen]);

  const choose = (option: string) => {
    if (picked !== null) return;
    setPicked(option);
    if (option !== correct) {
      notify('error');
      setRating(WRONG);
      return;
    }
    notify('success');
    const result = listen && revealed ? ALMOST : RIGHT;
    timer.current = window.setTimeout(() => onDone([{ card, rating: result }]), ADVANCE_MS);
  };

  return (
    <>
      <div className="prompt">
        {listen && (
          <Button size="l" mode="bezeled" onClick={() => speak(card.word)}>
            🔊 Ещё раз
          </Button>
        )}
        {revealed && (
          <LargeTitle weight="1" className="prompt__main">
            {direction === 'en-ru' ? title(card) : card.translation}
          </LargeTitle>
        )}
        {listen && !revealed && (
          <button type="button" className="link" onClick={() => setRevealed(true)}>
            Не слышно — показать слово
          </button>
        )}
        {direction === 'en-ru' && revealed && card.ipa && (
          <Caption className="hint">/{card.ipa}/</Caption>
        )}
        {direction === 'ru-en' && POS_HINTS[card.pos] && (
          <Caption className="hint">{POS_HINTS[card.pos]}</Caption>
        )}
      </div>

      <div className="options">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={optionClass(option, picked, correct)}
            disabled={picked !== null}
            onClick={() => choose(option)}
          >
            <Text>{option}</Text>
          </button>
        ))}
      </div>

      {rating === WRONG && (
        <Feedback card={card} rating={WRONG} onNext={() => onDone([{ card, rating: WRONG }])} />
      )}
    </>
  );
}

function optionClass(option: string, picked: string | null, correct: string): string {
  if (picked === null) return 'option';
  if (option === correct) return 'option option--right';
  if (option === picked) return 'option option--wrong';
  return 'option option--dim';
}
