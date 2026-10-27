import { AppRoot, Button, Placeholder, Spinner } from '@telegram-apps/telegram-ui';

import { useReviewSession } from './features/review/useReviewSession';
import { ReviewScreen } from './features/review/ReviewScreen';
import { SessionSummary } from './features/review/SessionSummary';
import { appearance, platform } from './lib/telegram';

export function App() {
  const { state, flip, rate, reload, learnNew } = useReviewSession();

  return (
    <AppRoot appearance={appearance} platform={platform}>
      {render()}
    </AppRoot>
  );

  function render() {
    switch (state.phase) {
      case 'loading':
        return (
          <div className="screen screen--center">
            <Spinner size="l" />
          </div>
        );

      case 'error':
        return (
          <Placeholder header="Не открылось" description={state.error} className="screen">
            <Button size="l" onClick={reload}>
              Повторить
            </Button>
          </Placeholder>
        );

      case 'empty':
        return (
          <Placeholder
            header="Свои слова на сегодня всё"
            description="Взять новые из общего словаря? Сначала те, что учат чаще всего."
            className="screen"
          >
            <Button size="l" mode="filled" onClick={learnNew}>
              Давай
            </Button>
          </Placeholder>
        );

      case 'exhausted':
        return (
          <Placeholder
            header="Новых слов нет"
            description="Ты разобрал весь общий словарь. Пришли боту своё слово."
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
          />
        );
      }

      case 'done':
        return (
          <SessionSummary
            done={state.cards.length}
            lapses={state.lapses}
            syncErrors={state.syncErrors}
            onRestart={reload}
          />
        );
    }
  }
}
