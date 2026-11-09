import { Button, Caption, Placeholder, Progress, Spinner } from '@telegram-apps/telegram-ui';

import type { QuizCard } from '../../api/types';
import { POS_NAMES } from '../../lib/word';
import { SessionSummary } from '../review/SessionSummary';
import { acceptedWords } from './check';
import { Choice } from './exercises/Choice';
import { FormChoice } from './exercises/FormChoice';
import { Forms } from './exercises/Forms';
import { Pairs } from './exercises/Pairs';
import { Typing } from './exercises/Typing';
import { type Mode } from './modes';
import { type Result, useQuizSession } from './useQuizSession';

interface Props {
  mode: Mode;
  onCards: () => void;
  onLeaderboard: () => void;
}

/** Состояние FSRS «выучено»: такой глагол спрашиваем вводом, а не выбором. */
const REVIEW = 2;

const EMPTY: Partial<Record<Mode['id'], string>> = {
  irregular: 'В твоих словах пока нет неправильных глаголов. Возьми их набором «Неправильные глаголы» на главной.',
  cloze: 'Ни в одном примере твоих слов не нашлось формы слова. Попробуй другой тест.',
};

export function QuizFlow({ mode, onCards, onLeaderboard }: Props) {
  const session = useQuizSession(mode);

  switch (session.phase) {
    case 'loading':
      return (
        <div className="screen screen--center">
          <Spinner size="l" />
        </div>
      );

    case 'error':
      return (
        <Placeholder
          header="Не открылось"
          description={session.error}
          className="screen"
          action={<Button size="l" onClick={session.reload}>Повторить</Button>}
        />
      );

    case 'empty':
      return (
        <Placeholder
          header="Тестировать пока нечего"
          description={EMPTY[mode.id] ?? 'Тесты берут слова, которые ты уже видел. Сначала пройди карточки.'}
          className="screen"
          action={<Button size="l" onClick={onCards}>К карточкам</Button>}
        />
      );

    case 'done':
      return (
        <SessionSummary
          done={session.answered}
          lapses={session.lapses}
          syncErrors={session.syncErrors}
          settled={session.settled}
          onRestart={session.reload}
          onLeaderboard={onLeaderboard}
        />
      );

    case 'play':
      return (
        <div className="screen">
          <header className="screen__head">
            <Progress value={(session.index / session.total) * 100} />
            <Caption className="screen__counter">
              {mode.icon} {session.index + 1}/{session.total}
            </Caption>
          </header>
          <main className="quiz">
            {/* key: новый раунд — новое состояние упражнения, без ручного сброса. */}
            <Exercise key={session.index} mode={mode} round={session.round} onDone={session.finish} />
          </main>
        </div>
      );
  }
}

interface ExerciseProps {
  mode: Mode;
  round: QuizCard[];
  onDone: (results: Result[]) => void;
}

function Exercise({ mode, round, onDone }: ExerciseProps) {
  const [card] = round;
  if (!card) return null;
  switch (mode.id) {
    case 'en-ru':
      return <Choice card={card} direction="en-ru" onDone={onDone} />;
    case 'ru-en':
      return <Choice card={card} direction="ru-en" onDone={onDone} />;
    case 'listen':
      return <Choice card={card} direction="en-ru" listen onDone={onDone} />;
    case 'pairs':
      return <Pairs round={round} onDone={onDone} />;
    case 'irregular':
      return card.state === REVIEW ? <Forms card={card} onDone={onDone} /> : <FormChoice card={card} onDone={onDone} />;
    case 'spell':
      return (
        <Typing
          card={card}
          question={card.translation}
          caption={POS_NAMES[card.pos] ?? card.pos}
          accepted={acceptedWords(card)}
          onDone={onDone}
        />
      );
    case 'cloze': {
      // fits режима гарантирует cloze; проверка — для типов.
      if (!card.cloze) return null;
      return (
        <Typing
          card={card}
          question={card.cloze.text}
          caption={`${card.cloze.ru} · ${card.translation}`}
          accepted={[card.cloze.answer]}
          near={[card.word]}
          onDone={onDone}
        />
      );
    }
  }
}
