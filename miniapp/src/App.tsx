import { AppRoot, Button, Placeholder, Spinner } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import { LeaderboardScreen } from './features/leaderboard/LeaderboardScreen';
import { useReviewSession } from './features/review/useReviewSession';
import { ReviewScreen } from './features/review/ReviewScreen';
import { SessionSummary } from './features/review/SessionSummary';
import { appearance, platform } from './lib/telegram';

export function App() {
  const { state, flip, rate, reload, learnNew, settled } = useReviewSession();
  // Рейтинг открывается поверх сессии, а не вместо неё: «Назад» возвращает
  // на тот же экран, а не перезагружает очередь.
  const [showBoard, setShowBoard] = useState(false);

  const boardButton = (
    <Button size="l" mode="plain" onClick={() => setShowBoard(true)}>
      🏆 Рейтинг недели
    </Button>
  );

  return (
    <AppRoot appearance={appearance} platform={platform}>
      {showBoard ? <LeaderboardScreen onBack={() => setShowBoard(false)} /> : render()}
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
          <Placeholder
            header="Не открылось"
            description={state.error}
            className="screen"
            action={
              <Button size="l" onClick={reload}>
                Повторить
              </Button>
            }
          />
        );

      case 'empty':
        return (
          <Placeholder
            header="Свои слова на сегодня всё"
            description="Взять новые из общего словаря? Сначала те, что учат чаще всего."
            className="screen"
            action={
              <div className="actions">
                <Button size="l" mode="filled" onClick={learnNew}>
                  Давай
                </Button>
                {boardButton}
              </div>
            }
          />
        );

      case 'exhausted':
        return (
          <Placeholder
            header="Новых слов нет"
            description="Ты разобрал весь общий словарь. Пришли боту своё слово."
            className="screen"
            action={boardButton}
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
            settled={settled}
            onRestart={reload}
            onLeaderboard={() => setShowBoard(true)}
          />
        );
    }
  }
}
