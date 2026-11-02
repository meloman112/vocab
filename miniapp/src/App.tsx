import { AppRoot } from '@telegram-apps/telegram-ui';
import { useCallback, useState } from 'react';

import { AdminScreen } from './features/admin/AdminScreen';
import { HomeScreen } from './features/home/HomeScreen';
import { LeaderboardScreen } from './features/leaderboard/LeaderboardScreen';
import { modeById, type ModeId } from './features/quiz/modes';
import { QuizFlow } from './features/quiz/QuizFlow';
import { CardsFlow } from './features/review/CardsFlow';
import { appearance, platform, useBackButton } from './lib/telegram';

type Screen = { name: 'home' } | { name: 'cards' } | { name: 'quiz'; mode: ModeId } | { name: 'admin' };

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'home' });
  // Рейтинг открывается поверх экрана, а не вместо него: сессия под ним
  // остаётся смонтированной, и «Назад» возвращает в то же место.
  const [showBoard, setShowBoard] = useState(false);

  const home = useCallback(() => setScreen({ name: 'home' }), []);
  const cards = useCallback(() => setScreen({ name: 'cards' }), []);
  const openBoard = useCallback(() => setShowBoard(true), []);
  const closeBoard = useCallback(() => setShowBoard(false), []);

  // Админка ведёт «Назад» сама: из редактора слова — в список, а не в меню.
  const ownBack = screen.name === 'home' || screen.name === 'admin';
  useBackButton(showBoard ? closeBoard : ownBack ? null : home);

  return (
    <AppRoot appearance={appearance} platform={platform}>
      <div hidden={showBoard}>{render()}</div>
      {showBoard && <LeaderboardScreen onBack={closeBoard} />}
    </AppRoot>
  );

  function render() {
    switch (screen.name) {
      case 'home':
        return (
          <HomeScreen
            onCards={cards}
            onQuiz={(mode) => setScreen({ name: 'quiz', mode })}
            onLeaderboard={openBoard}
            onAdmin={() => setScreen({ name: 'admin' })}
          />
        );
      case 'cards':
        return <CardsFlow onLeaderboard={openBoard} />;
      case 'quiz':
        return <QuizFlow key={screen.mode} mode={modeById(screen.mode)} onCards={cards} onLeaderboard={openBoard} />;
      case 'admin':
        return <AdminScreen onExit={home} />;
    }
  }
}
