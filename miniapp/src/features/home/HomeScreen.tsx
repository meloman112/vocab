import { Badge, Cell, List, Section, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { Me, Stats, StudentTest } from '../../api/types';
import { MODES, type ModeId } from '../quiz/modes';

interface Props {
  onGrammar: () => void;
  onTeacher: () => void;
  onTests: () => void;
  onCards: () => void;
  onDeck: (deck: string) => void;
  onQuiz: (mode: ModeId) => void;
  onLeaderboard: () => void;
  onAdmin: () => void;
}

interface Header {
  stats: Stats;
  me: Me;
  /** null — не админ; число — открытые жалобы. */
  reports: number | null;
}

export function HomeScreen({ onGrammar, onTeacher, onTests, onCards, onDeck, onQuiz, onLeaderboard, onAdmin }: Props) {
  const [header, setHeader] = useState<Header | null>(null);
  const [error, setError] = useState('');
  const [tests, setTests] = useState<StudentTest[]>([]);

  useEffect(() => {
    Promise.all([api.stats(), api.me()])
      .then(async ([stats, me]) => ({
        stats,
        me,
        reports: me.is_admin ? (await api.admin.summary()).open_reports : null,
      }))
      .then(setHeader, (e: Error) => setError(e.message));
    api.tests.list().then(setTests, (e: Error) => setError(e.message));
  }, []);

  const todo = tests.filter((t) => !t.submitted_at && !t.closed).length;

  const due = header?.stats.due_now ?? 0;
  const me = header?.me;

  return (
    <div className="screen screen--list">
      <List>
        <Section header="Грамматика" footer="134 упражнения из Work book: каждую ошибку разбираем, учитель её видит.">
          <Cell
            before={<Icon>📒</Icon>}
            subtitle={me ? (me.grammar_done ? `Сделано ${me.grammar_done} заданий` : 'От Present Simple до Participle') : undefined}
            after={me && me.grammar_wrong > 0 ? <Badge type="number" mode="critical">{me.grammar_wrong}</Badge> : undefined}
            onClick={onGrammar}
          >
            Тетрадь
          </Cell>
          {tests.length > 0 && (
            <Cell before={<Icon>📝</Icon>} onClick={onTests}
              subtitle={todo ? `Нужно сдать: ${todo}` : 'Все тесты сданы'}
              after={todo ? <Badge type="number" mode="critical">{todo}</Badge> : undefined}>
              Тесты от учителя
            </Cell>
          )}
        </Section>

        <Section
          header="Слова"
          footer={error ? `Цифры не загрузились: ${error}` : streakLine(header?.stats)}
        >
          <Cell
            before={<Icon>🧠</Icon>}
            subtitle={due > 0 ? `Ждут повторения: ${due}` : 'Новые слова из общего словаря'}
            after={due > 0 ? <Badge type="number">{due}</Badge> : undefined}
            onClick={onCards}
          >
            Карточки
          </Cell>
          {/* Тап — следующие 10 слов набора в свои карточки, сразу на изучение. */}
          {header?.stats.decks.map((deck) => (
            <Cell
              key={deck.deck}
              before={<Icon>📘</Icon>}
              subtitle={`Изучено ${deck.learned} из ${deck.total} · учить следующие 10`}
              multiline
              onClick={() => onDeck(deck.deck)}
            >
              {deck.deck}
            </Cell>
          ))}
        </Section>

        <Section header="Тесты" footer="Ответ в тесте засчитывается как повторение: ошибся — слово вернётся скорее.">
          {MODES.map((mode) => (
            <Cell
              key={mode.id}
              before={<Icon>{mode.icon}</Icon>}
              subtitle={mode.subtitle}
              onClick={() => onQuiz(mode.id)}
            >
              {mode.title}
            </Cell>
          ))}
        </Section>

        <Section>
          <Cell before={<Icon>🏆</Icon>} onClick={onLeaderboard}>
            Рейтинг недели
          </Cell>
          {me?.is_teacher && (
            <Cell before={<Icon>👩‍🏫</Icon>} subtitle="Ошибки в тетради, классы и тесты" onClick={onTeacher}>
              Ученики
            </Cell>
          )}
          {header?.reports != null && (
            <Cell
              before={<Icon>🛠</Icon>}
              after={header.reports > 0 ? <Badge type="number" mode="critical">{header.reports}</Badge> : undefined}
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

function streakLine(stats: Stats | undefined): string | undefined {
  if (!stats) return undefined;
  return `🔥 Серия: ${stats.streak} дн. · рекорд ${stats.best_streak}`;
}
