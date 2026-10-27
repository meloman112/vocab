import {
  Button,
  Cell,
  List,
  Placeholder,
  Section,
  Spinner,
  Text,
} from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { Leaderboard, LeaderRow } from '../../api/types';

interface Props {
  onBack: () => void;
}

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

export function LeaderboardScreen({ onBack }: Props) {
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.leaderboard().then(setBoard, (e: Error) => setError(e.message));
  }, []);

  const back = (
    <Button size="l" mode="bezeled" onClick={onBack}>
      Назад
    </Button>
  );

  if (error) {
    return (
      <Placeholder header="Не открылось" description={error} className="screen" action={back} />
    );
  }
  if (!board) {
    return (
      <div className="screen screen--center">
        <Spinner size="l" />
      </div>
    );
  }

  // Кнопка вне List: внутри его flex-колонки она растягивается на всю высоту.
  return (
    <div className="screen">
      <List>
        <Section header="Рейтинг недели" footer="10 XP за повторение. Обнуляется в понедельник.">
          {board.top.length === 0 && <Cell>Пока никого — будь первым</Cell>}
          {/* Индекс, а не place+name: при равном XP место общее, имена повторяются. */}
          {board.top.map((row, i) => (
            <Row key={i} row={row} />
          ))}
        </Section>
        {/* Своя строка отдельно — только когда в топ не попал. */}
        {board.me && !inTop(board, board.me) && (
          <Section header="Ты">
            <Row row={board.me} />
          </Section>
        )}
      </List>
      {back}
    </div>
  );
}

function inTop(board: Leaderboard, me: LeaderRow): boolean {
  const last = board.top[board.top.length - 1];
  return last !== undefined && me.place <= last.place;
}

function Row({ row }: { row: LeaderRow }) {
  return (
    <Cell
      before={<Text className="place">{MEDALS[row.place] ?? row.place}</Text>}
      // Text, а не строка: голая строка в after не получает шрифт темы.
      after={<Text>{row.xp} XP</Text>}
      subtitle={row.streak > 0 ? `🔥 ${row.streak} дн. подряд` : undefined}
    >
      {row.name}
    </Cell>
  );
}
