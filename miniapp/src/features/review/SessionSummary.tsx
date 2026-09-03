import { Button, Placeholder } from '@telegram-apps/telegram-ui';

interface Props {
  done: number;
  lapses: number;
  syncErrors: number;
  onRestart: () => void;
}

export function SessionSummary({ done, lapses, syncErrors, onRestart }: Props) {
  const description = [
    `Повторено: ${done}`,
    `Ошибок: ${lapses}`,
    // Про несохранённые оценки нужно сказать: карточка визуально ушла,
    // но её расписание не сдвинулось, и она вернётся в следующей очереди.
    syncErrors > 0 ? `Не сохранилось: ${syncErrors}` : '',
  ]
    .filter(Boolean)
    .join('\n');

  return (
    <Placeholder header="Готово" description={description} className="screen">
      <Button size="l" mode="filled" onClick={onRestart}>
        Ещё
      </Button>
    </Placeholder>
  );
}
