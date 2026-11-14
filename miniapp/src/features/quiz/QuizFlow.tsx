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
import { useLearnSession } from './useLearnSession';
import { type Mode, modeById } from './modes';
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
  learn: 'Слов пока нет. Возьми новые на главной или пришли боту английское слово.',
  cloze: 'Ни в одном примере твоих слов не нашлось формы слова. Попробуй другой тест.',
};

type Session = ReturnType<typeof useQuizSession> | ReturnType<typeof useLearnSession>;

export function QuizFlow(props: Props) {
  return props.mode.id === 'learn' ? <LearnFlow {...props} /> : <TestFlow {...props} />;
}

function TestFlow(props: Props) {
  return <Flow {...props} session={useQuizSession(props.mode)} />;
}

function LearnFlow(props: Props) {
  return <Flow {...props} session={useLearnSession()} />;
}

function Flow({ mode, onCards, onLeaderboard, session }: Props & { session: Session }) {
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
            <Progress value={session.progress * 100} />
            <Caption className="screen__counter">
              {mode.icon} {session.counter}
            </Caption>
          </header>
          <main className="quiz">
            {/* key: новый раунд — новое состояние упражнения, без ручного сброса.
                В тренировке упражнение — текущая ступенька слова. */}
            <Exercise
              key={session.turn}
              mode={session.step ? modeById(session.step) : mode}
              round={session.round}
              secondChance={session.step !== null}
              onDone={session.finish}
            />
          </main>
        </div>
      );
  }
}

interface ExerciseProps {
  mode: Mode;
  round: QuizCard[];
  /** Первая ошибка в вводе — подсказка и ещё попытка, а не провал. */
  secondChance: boolean;
  onDone: (results: Result[]) => void;
}

function Exercise({ mode, round, secondChance, onDone }: ExerciseProps) {
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
    case 'learn':
      throw new Error('тренировка — это лесенка из других режимов');
    case 'irregular':
      return card.state === REVIEW ? <Forms card={card} onDone={onDone} /> : <FormChoice card={card} onDone={onDone} />;
    case 'spell':
      return (
        <Typing
          card={card}
          question={card.translation}
          caption={POS_NAMES[card.pos] ?? card.pos}
          accepted={acceptedWords(card)}
          secondChance={secondChance}
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
          secondChance={secondChance}
          onDone={onDone}
        />
      );
    }
  }
}
