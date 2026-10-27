import { Button, Placeholder } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import { XP_PER_REVIEW, type Leaderboard, type Stats } from '../../api/types';

interface Props {
  done: number;
  lapses: number;
  syncErrors: number;
  /** Резолвится, когда все оценки сессии доехали до сервера. */
  settled: () => Promise<unknown>;
  onRestart: () => void;
  onLeaderboard: () => void;
}

interface Progress {
  stats: Stats;
  board: Leaderboard;
}

export function SessionSummary({
  done,
  lapses,
  syncErrors,
  settled,
  onRestart,
  onLeaderboard,
}: Props) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [progressError, setProgressError] = useState('');

  useEffect(() => {
    settled()
      .then(() => Promise.all([api.stats(), api.leaderboard()]))
      .then(([stats, board]) => setProgress({ stats, board }))
      .catch((error: Error) => setProgressError(error.message));
  }, [settled]);

  const lines = [
    `Повторено: ${done}`,
    `Ошибок: ${lapses}`,
    // Про несохранённые оценки нужно сказать: карточка визуально ушла,
    // но её расписание не сдвинулось, и она вернётся в следующей очереди.
    syncErrors > 0 ? `Не сохранилось: ${syncErrors}` : '',
    `+${(done - syncErrors) * XP_PER_REVIEW} XP`,
    ...progressLines(progress),
    progressError ? `Серия и рейтинг не загрузились: ${progressError}` : '',
  ].filter(Boolean);

  return (
    <Placeholder
      header="Готово"
      description={lines.map((line) => (
        <div key={line}>{line}</div>
      ))}
      className="screen"
      action={
        <div className="actions">
          <Button size="l" mode="filled" onClick={onRestart}>
            Ещё
          </Button>
          <Button size="l" mode="plain" onClick={onLeaderboard}>
            🏆 Рейтинг недели
          </Button>
        </div>
      }
    />
  );
}

function progressLines(progress: Progress | null): string[] {
  if (!progress) return [];
  const { stats, board } = progress;
  return [
    `🔥 Серия: ${stats.streak} дн. (рекорд ${stats.best_streak})`,
    board.me ? `За неделю: ${board.me.xp} XP · ${board.me.place} место` : '',
  ];
}
