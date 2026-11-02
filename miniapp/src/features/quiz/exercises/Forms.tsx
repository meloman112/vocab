import { Button, Caption, Input, LargeTitle } from '@telegram-apps/telegram-ui';
import { type FormEvent, useState } from 'react';

import type { QuizCard, Rating } from '../../../api/types';
import { notify } from '../../../lib/telegram';
import { ALMOST, irregularForms, normalize, RIGHT, WRONG } from '../check';
import { Feedback } from '../Feedback';
import type { Result } from '../useQuizSession';

/** go → went, gone. Опечатка в форме — ошибка: форму и учат по буквам. */
export function Forms({ card, onDone }: { card: QuizCard; onDone: (results: Result[]) => void }) {
  const { v2, v3 } = irregularForms(card.forms);
  const [past, setPast] = useState('');
  const [participle, setParticiple] = useState('');
  const [checked, setChecked] = useState<{ v2: boolean; v3: boolean } | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (checked) return;
    const result = { v2: v2.includes(normalize(past)), v3: v3.includes(normalize(participle)) };
    notify(result.v2 && result.v3 ? 'success' : 'error');
    setChecked(result);
  };

  const rating: Rating = !checked ? WRONG : checked.v2 && checked.v3 ? RIGHT : checked.v2 || checked.v3 ? ALMOST : WRONG;

  return (
    <>
      <div className="prompt">
        <LargeTitle weight="1" className="prompt__main">
          {card.word}
        </LargeTitle>
        <Caption className="hint">{card.translation}</Caption>
      </div>

      <form onSubmit={submit} className="answer">
        <Input
          placeholder="V2 — Past Simple"
          value={past}
          onChange={(e) => setPast(e.target.value)}
          status={checked ? (checked.v2 ? 'focused' : 'error') : 'default'}
          disabled={checked !== null}
          autoFocus
          autoCapitalize="off"
          autoCorrect="off"
          autoComplete="off"
          spellCheck={false}
        />
        <Input
          placeholder="V3 — Past Participle"
          value={participle}
          onChange={(e) => setParticiple(e.target.value)}
          status={checked ? (checked.v3 ? 'focused' : 'error') : 'default'}
          disabled={checked !== null}
          autoCapitalize="off"
          autoCorrect="off"
          autoComplete="off"
          spellCheck={false}
        />
        {!checked && (
          <Button size="l" type="submit" stretched disabled={!past.trim() || !participle.trim()}>
            Проверить
          </Button>
        )}
      </form>

      {checked && (
        <Feedback
          card={card}
          rating={rating}
          note={rating === RIGHT ? undefined : `правильно: ${card.forms}`}
          onNext={() => onDone([{ card, rating }])}
        />
      )}
    </>
  );
}
