import { Button, Caption, Input, LargeTitle, Text } from '@telegram-apps/telegram-ui';
import { type FormEvent, type ReactNode, useState } from 'react';

import type { QuizCard, Rating } from '../../../api/types';
import { celebrate } from '../../../lib/celebrate';
import { notify } from '../../../lib/telegram';
import { ALMOST, type Answers, type Grade, grade, hint, RIGHT, WRONG } from '../check';
import { Feedback } from '../Feedback';
import type { Result } from '../useQuizSession';

interface Props {
  card: QuizCard;
  /** Над полем: перевод или предложение с пропуском. */
  question: ReactNode;
  caption?: ReactNode;
  accepted: Answers;
  near?: string[];
  /** Первая ошибка — подсказка и ещё попытка (тренировка). */
  secondChance?: boolean;
  onDone: (results: Result[]) => void;
}

export function Typing({ card, question, caption, accepted, near, secondChance = false, onDone }: Props) {
  const [value, setValue] = useState('');
  const [hinted, setHinted] = useState(false);
  const [missed, setMissed] = useState(false);
  const [result, setResult] = useState<Grade | null>(null);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (result || !value.trim()) return;
    const graded = grade(value, accepted, near);
    if (graded.rating === WRONG && secondChance && !missed) {
      notify('warning');
      setMissed(true);
      setHinted(true);
      setValue('');
      return;
    }
    // С подсказкой верный ответ — уже не чистое воспоминание.
    const rating: Rating = hinted ? (Math.min(graded.rating, ALMOST) as Rating) : graded.rating;
    notify(rating === RIGHT ? 'success' : rating === WRONG ? 'error' : 'warning');
    if (rating === RIGHT) celebrate(event?.currentTarget as Element | undefined);
    setResult({ rating, note: noteFor(graded, hinted, accepted[0]) });
  };

  const giveUp = () => {
    notify('error');
    setResult({ rating: WRONG, note: `правильно: ${accepted[0]}` });
  };

  return (
    <>
      <div className="prompt">
        <LargeTitle weight="1" className="prompt__main prompt__main--text">
          {question}
        </LargeTitle>
        {caption && <Caption className="hint">{caption}</Caption>}
        {missed && !result && <Text>Не-а 😑 Подсказка:</Text>}
        {hinted && <Text className="mono">{hint(accepted[0])}</Text>}
      </div>

      <form onSubmit={submit} className="answer">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="по-английски"
          disabled={result !== null}
          status={result ? (result.rating === WRONG ? 'error' : 'focused') : 'default'}
          autoFocus
          autoCapitalize="off"
          autoCorrect="off"
          autoComplete="off"
          spellCheck={false}
          enterKeyHint="done"
        />
        {!result && (
          <div className="answer__actions">
            <Button size="l" type="submit" stretched disabled={!value.trim()}>
              Проверить
            </Button>
            <div className="answer__row">
              <Button size="m" mode="plain" type="button" disabled={hinted} onClick={() => setHinted(true)}>
                Подсказка
              </Button>
              <Button size="m" mode="plain" type="button" onClick={giveUp}>
                Не знаю
              </Button>
            </div>
          </div>
        )}
      </form>

      {result && (
        <Feedback
          card={card}
          rating={result.rating}
          note={result.note}
          onNext={() => onDone([{ card, rating: result.rating }])}
        />
      )}
    </>
  );
}

function noteFor(graded: Grade, hinted: boolean, answer: string): string | undefined {
  if (graded.rating === WRONG) return `правильно: ${answer}`;
  if (hinted && graded.rating === RIGHT) return 'с подсказкой';
  return graded.note;
}
