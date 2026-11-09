import { Button, Caption } from '@telegram-apps/telegram-ui';

import type { Card, Rating } from '../../api/types';

interface Props {
  card: Card;
  disabled: boolean;
  onRate: (rating: Rating) => void;
  onKnown: () => void;
}

const relative = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' });

/** «через 10 минут», «завтра», «через 3 дня» — крупнейшей целой единицей. */
function fromNow(iso: string): string {
  const minutes = Math.max(1, Math.round((Date.parse(iso) - Date.now()) / 60_000));
  if (minutes < 60) return relative.format(minutes, 'minute');
  const hours = Math.round(minutes / 60);
  if (hours < 24) return relative.format(hours, 'hour');
  return relative.format(Math.round(hours / 24), 'day');
}

/**
 * Три понятных исхода вместо четырёх оценок FSRS: под каждой кнопкой
 * написано, что будет. Hard и Easy почти не нажимали, а FSRS с Again и
 * Good работает штатно.
 */
export function RatingBar({ card, disabled, onRate, onKnown }: Props) {
  return (
    <div className="ratings">
      <div className="rating">
        <Button size="l" mode="gray" stretched disabled={disabled} onClick={() => onRate(1)}>
          Не помню
        </Button>
        <Caption className="rating__hint">повторю скоро</Caption>
      </div>
      <div className="rating">
        <Button size="l" mode="filled" stretched disabled={disabled} onClick={() => onRate(3)}>
          Помню
        </Button>
        <Caption className="rating__hint">{fromNow(card.remembered_due)}</Caption>
      </div>
      <div className="rating">
        <Button size="l" mode="bezeled" stretched disabled={disabled} onClick={onKnown}>
          Знаю
        </Button>
        <Caption className="rating__hint">больше не покажу</Caption>
      </div>
    </div>
  );
}
