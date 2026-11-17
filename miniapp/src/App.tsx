import { AppRoot, Tabbar } from '@telegram-apps/telegram-ui';
import { useCallback, useEffect, useState } from 'react';

import { AdminScreen } from './features/admin/AdminScreen';
import { ClassScreen } from './features/class/ClassScreen';
import { GrammarScreen } from './features/grammar/GrammarScreen';
import { LeaderboardScreen } from './features/leaderboard/LeaderboardScreen';
import { MODES, modeById, type ModeId } from './features/quiz/modes';
import { QuizFlow } from './features/quiz/QuizFlow';
import { CardsFlow } from './features/review/CardsFlow';
import { TestsScreen } from './features/tests/TestsScreen';
import { TodayScreen } from './features/today/TodayScreen';
import { useSummary } from './features/today/useSummary';
import { SelectionTranslate } from './features/translate/SelectionTranslate';
import { WordsScreen } from './features/words/WordsScreen';
import { ErrorBoundary } from './lib/errors';
import { appearance, platform, startScreen, startTestId, useBackButton, useHasBack } from './lib/telegram';

const TABS = [
  { id: 'today', icon: '🏠', text: 'Сегодня' },
  { id: 'grammar', icon: '📒', text: 'Грамматика' },
  { id: 'words', icon: '🧠', text: 'Слова' },
  { id: 'class', icon: '👩‍🏫', text: 'Класс' },
] as const;

type Tab = (typeof TABS)[number]['id'];

/** Открыто поверх вкладки; «Назад» возвращает на неё. */
type Flow =
  | { name: 'cards'; deck?: string }
  | { name: 'quiz'; mode: ModeId }
  | { name: 'test'; id: number }
  | { name: 'admin' };

const startMode = MODES.find((m) => m.id === startScreen);

/** Кнопки бота открывают мини-апп сразу на нужном разделе: ?screen=grammar. */
function initialTab(): Tab {
  if (startScreen === 'grammar') return 'grammar';
  if (startScreen === 'teacher' || startScreen === 'tests' || startScreen === 'test') return 'class';
  if (startScreen === 'cards' || startMode) return 'words';
  return 'today';
}

function initialFlow(): Flow | null {
  if (startScreen === 'cards') return { name: 'cards' };
  if ((startScreen === 'tests' || startScreen === 'test') && startTestId) return { name: 'test', id: startTestId };
  if (startMode) return { name: 'quiz', mode: startMode.id };
  return null;
}

export function App() {
  const [tab, setTab] = useState(initialTab);
  const [flow, setFlow] = useState(initialFlow);
  // Рейтинг открывается поверх экрана, а не вместо него: сессия под ним
  // остаётся смонтированной, и «Назад» возвращает в то же место.
  const [showBoard, setShowBoard] = useState(false);
  const { summary, reload } = useSummary();
  // Панель вкладок — только на корне вкладки: внутри упражнения, теста и
  // карточек она отнимала бы место и уводила бы из сессии случайным тапом.
  const tabbar = !useHasBack() && !flow;

  const closeFlow = useCallback(() => setFlow(null), []);
  const cards = useCallback(() => setFlow({ name: 'cards' }), []);
  const openBoard = useCallback(() => setShowBoard(true), []);
  const closeBoard = useCallback(() => setShowBoard(false), []);

  // Тест и админка ведут «Назад» сами: у них своя навигация внутри.
  const ownBack = flow?.name === 'test' || flow?.name === 'admin';
  useBackButton(showBoard ? closeBoard : flow && !ownBack ? closeFlow : null);

  // Счётчики меняются в карточках, тестах и тетради — по возвращении перечитываем.
  useEffect(() => {
    if (!flow && tab !== 'grammar') reload();
  }, [flow, tab, reload]);

  // Фигурные скобки обязательны: Promise от scrollTo стал бы «очисткой» эффекта.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [flow, tab]);

  return (
    <AppRoot appearance={appearance} platform={platform}>
      {/* key — экран: ошибка одного раздела не держит сломанным остальные. */}
      <ErrorBoundary key={flow?.name ?? tab}>
        <div hidden={showBoard} className={tabbar ? 'tabs' : undefined}>
          {flow ? renderFlow(flow) : renderTab()}
        </div>
        {showBoard && <LeaderboardScreen inClass={summary.me?.in_class ?? false} onBack={closeBoard} />}
      </ErrorBoundary>
      {tabbar && (
        <Tabbar>
          {TABS.map((t) => (
            <Tabbar.Item key={t.id} className="tab" text={t.text} selected={tab === t.id} onClick={() => setTab(t.id)}>
              <span className="icon">{t.icon}</span>
            </Tabbar.Item>
          ))}
        </Tabbar>
      )}
      {/* Поверх любого экрана: выделил слово — перевод. Своя граница, чтобы
          сбой перевода не ронял открытый раздел. */}
      <ErrorBoundary>
        <SelectionTranslate />
      </ErrorBoundary>
    </AppRoot>
  );

  function renderTab() {
    switch (tab) {
      case 'today':
        return (
          <TodayScreen
            summary={summary}
            onTest={(id) => setFlow({ name: 'test', id })}
            onClass={() => setTab('class')}
            onCards={cards}
            onGrammar={() => setTab('grammar')}
            onLeaderboard={openBoard}
            onAdmin={() => setFlow({ name: 'admin' })}
          />
        );
      case 'grammar':
        return <GrammarScreen />;
      case 'words':
        return (
          <WordsScreen
            stats={summary.stats}
            error={summary.error}
            onCards={cards}
            onDeck={(deck) => setFlow({ name: 'cards', deck })}
            onQuiz={(mode) => setFlow({ name: 'quiz', mode })}
          />
        );
      case 'class':
        return (
          <ClassScreen me={summary.me} tests={summary.tests} error={summary.error}
            startTests={startScreen === 'tests'} onChanged={reload} />
        );
    }
  }

  function renderFlow(flow: Flow) {
    switch (flow.name) {
      case 'cards':
        // key — набор: переход из одного набора в другой начинает сессию заново.
        return (
          <CardsFlow
            key={flow.deck}
            deck={flow.deck}
            onLeaderboard={openBoard}
            onDrill={() => setFlow({ name: 'quiz', mode: 'irregular' })}
          />
        );
      case 'quiz':
        return <QuizFlow key={flow.mode} mode={modeById(flow.mode)} onCards={cards} onLeaderboard={openBoard} />;
      case 'test':
        return <TestsScreen openId={flow.id} onExit={closeFlow} />;
      case 'admin':
        return <AdminScreen onExit={closeFlow} />;
    }
  }
}
