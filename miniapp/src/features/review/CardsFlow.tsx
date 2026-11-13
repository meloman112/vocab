import { Button, Placeholder, Snackbar, Spinner } from '@telegram-apps/telegram-ui';

import { ReviewScreen } from './ReviewScreen';
import { SessionSummary } from './SessionSummary';
import { useReviewSession } from './useReviewSession';

/** Совпадает с repo.IRREGULAR_DECK: после этого набора предлагаем тест форм. */
const IRREGULAR_DECK = 'Неправильные глаголы';

interface Props {
  deck?: string;
  onLeaderboard: () => void;
  onDrill: () => void;
}

/** Повторение карточками: «Не помню», «Помню», «Знаю». */
export function CardsFlow({ deck, onLeaderboard, onDrill }: Props) {
  const session = useReviewSession(deck);
  const { known, undoKnown, dismissKnown } = session;
  return (
    <>
      <Phase session={session} deck={deck} onLeaderboard={onLeaderboard} onDrill={deck === IRREGULAR_DECK ? onDrill : undefined} />
      {/* Случайное «Знаю» иначе не исправить: слово просто исчезло бы. */}
      {known && (
        <Snackbar
          key={known.id}
          duration={5000}
          onClose={dismissKnown}
          description="больше не покажу"
          after={<Snackbar.Button onClick={undoKnown}>Отменить</Snackbar.Button>}
        >
          {known.word}
        </Snackbar>
      )}
    </>
  );
}

function Phase({
  session,
  deck,
  onLeaderboard,
  onDrill,
}: {
  session: ReturnType<typeof useReviewSession>;
  deck?: string;
  onLeaderboard: () => void;
  onDrill?: () => void;
}) {
  const { state, flip, rate, markKnown, reload, learnNew, settled } = session;

  switch (state.phase) {
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
          description={state.error}
          className="screen"
          action={<Button size="l" onClick={reload}>Повторить</Button>}
        />
      );

    case 'empty':
      return (
        <Placeholder
          header="Свои слова на сегодня всё"
          description="Взять новые из общего словаря? Сначала те, что учат чаще всего."
          className="screen"
          action={<Button size="l" mode="filled" onClick={learnNew}>Давай</Button>}
        />
      );

    case 'exhausted':
      return (
        <Placeholder
          header="Новых слов нет"
          description={deck ? `Все слова набора «${deck}» уже у тебя в карточках.` : 'Ты разобрал весь общий словарь. Пришли боту своё слово.'}
          className="screen"
        />
      );

    case 'enough':
      return (
        <Placeholder
          header="На сегодня новых хватит"
          description="15 новых слов в день — больше в памяти не держится. Повтори взятые, завтра будут новые."
          className="screen"
        />
      );

    case 'review': {
      const card = state.cards[state.index];
      // Индекс за пределами массива недостижим: reducer переводит
      // сессию в 'done' в тот же переход, что и увеличивает индекс.
      if (!card) return null;
      return (
        <ReviewScreen
          card={card}
          index={state.index}
          total={state.cards.length}
          flipped={state.flipped}
          onFlip={flip}
          onRate={rate}
          onKnown={markKnown}
        />
      );
    }

    case 'done':
      return (
        <SessionSummary
          done={state.cards.length}
          lapses={state.lapses}
          syncErrors={state.syncErrors}
          settled={settled}
          onRestart={reload}
          onLeaderboard={onLeaderboard}
          onDrill={onDrill}
        />
      );
  }
}
