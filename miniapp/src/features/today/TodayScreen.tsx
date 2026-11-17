import { Badge, Button, Caption, Cell, List, Section, Text, Title } from '@telegram-apps/telegram-ui';

import { AUTHOR_CREDIT } from '../../lib/about';
import { deadline } from '../tests/TestsScreen';
import type { Summary } from './useSummary';

interface Props {
  summary: Summary;
  onTest: (id: number) => void;
  onClass: () => void;
  onCards: () => void;
  onGrammar: () => void;
  onLeaderboard: () => void;
  onAdmin: () => void;
}

/** «Что делать сейчас»: одна кнопка на самое срочное и короткий список остального. */
export function TodayScreen({ summary, onTest, onClass, onCards, onGrammar, onLeaderboard, onAdmin }: Props) {
  const { stats, me, tests, board, reports, error } = summary;
  const todo = tests?.filter((t) => !t.submitted_at && !t.closed) ?? [];
  const test = todo[0];
  const due = stats?.due_now ?? 0;
  const wrong = me?.grammar_wrong ?? 0;
  // Пока тесты и слова не пришли, кнопка не знает, что срочнее.
  const ready = error !== '' || (stats !== null && tests !== null);
  const isNew = stats?.best_streak === 0 && due === 0 && me?.grammar_done === 0 && !test;

  const next = test
    ? { hint: `Тест «${test.title}» · ${deadline(test)}`, go: () => onTest(test.id) }
    : due > 0
      ? { hint: `Слова ждут повторения: ${due}`, go: onCards }
      : { hint: 'Тетрадь: следующее упражнение', go: onGrammar };

  return (
    <div className="screen screen--list">
      <header className="tab-head">
        <Title level="1" weight="1">Сегодня</Title>
        {stats && !isNew && (
          <Text className="hint">
            🔥 {stats.streak} дн. подряд{board?.me ? ` · ${board.me.xp} XP за неделю · ${board.me.place} место` : ''}
          </Text>
        )}
        <Button size="l" stretched loading={!ready} onClick={next.go}>
          {isNew ? 'Начать' : 'Продолжить'}
        </Button>
        {ready && !isNew && <Caption className="hint tab-head__next">{next.hint}</Caption>}
        {isNew && (
          <Caption className="hint">
            Грамматика — тетрадь: 134 упражнения, каждую ошибку разбираем.
            <br />
            Слова — карточки и тренировки: слово возвращается, когда пора повторить.
          </Caption>
        )}
        {error && <Caption className="error">Не всё загрузилось: {error}</Caption>}
      </header>

      <List>
        {(todo.length > 1 || (test && due > 0) || wrong > 0) && (
          <Section header="Ещё на сегодня">
            {todo.length > 1 && (
              <Cell before={<Icon>📝</Icon>} after={<Badge type="number" mode="critical">{todo.length}</Badge>} onClick={onClass}>
                Тесты от учителя
              </Cell>
            )}
            {test && due > 0 && (
              <Cell before={<Icon>🧠</Icon>} after={<Badge type="number">{due}</Badge>} onClick={onCards}>
                Повторить слова
              </Cell>
            )}
            {wrong > 0 && (
              <Cell before={<Icon>📒</Icon>} after={<Badge type="number" mode="critical">{wrong}</Badge>} onClick={onGrammar}>
                Ошибки в тетради
              </Cell>
            )}
          </Section>
        )}

        <Section footer={`${AUTHOR_CREDIT}. Бесплатно, без подписок и рекламы.`}>
          <Cell before={<Icon>🏆</Icon>} onClick={onLeaderboard}>
            Рейтинг недели
          </Cell>
          {reports !== null && (
            <Cell
              before={<Icon>🛠</Icon>}
              after={reports > 0 ? <Badge type="number" mode="critical">{reports}</Badge> : undefined}
              onClick={onAdmin}
            >
              Админка
            </Cell>
          )}
        </Section>
      </List>
    </div>
  );
}

function Icon({ children }: { children: string }) {
  return <Text className="icon">{children}</Text>;
}
