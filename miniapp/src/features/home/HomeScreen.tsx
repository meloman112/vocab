import { Badge, Cell, List, Section, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { Stats } from '../../api/types';
import { MODES, type ModeId } from '../quiz/modes';

interface Props {
  onCards: () => void;
  onQuiz: (mode: ModeId) => void;
  onLeaderboard: () => void;
  onAdmin: () => void;
}

interface Header {
  stats: Stats;
  /** null — не админ; число — открытые жалобы. */
  reports: number | null;
}

export function HomeScreen({ onCards, onQuiz, onLeaderboard, onAdmin }: Props) {
  const [header, setHeader] = useState<Header | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.stats(), api.me()])
      .then(async ([stats, me]) => ({
        stats,
        reports: me.is_admin ? (await api.admin.summary()).open_reports : null,
      }))
      .then(setHeader, (e: Error) => setError(e.message));
  }, []);

  const due = header?.stats.due_now ?? 0;

  return (
    <div className="screen screen--list">
      <List>
        <Section
          header="Повторение"
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
