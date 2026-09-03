import { Button } from '@telegram-apps/telegram-ui';

import type { Rating } from '../../api/types';

interface Props {
  disabled: boolean;
  onRate: (rating: Rating) => void;
}

/** Порядок и подписи — как в FSRS: 1 Again, 2 Hard, 3 Good, 4 Easy. */
const BUTTONS: { rating: Rating; label: string; mode: 'gray' | 'bezeled' | 'filled' }[] = [
  { rating: 1, label: 'Again', mode: 'gray' },
  { rating: 2, label: 'Hard', mode: 'bezeled' },
  { rating: 3, label: 'Good', mode: 'filled' },
  { rating: 4, label: 'Easy', mode: 'bezeled' },
];

export function RatingBar({ disabled, onRate }: Props) {
  return (
    <div className="ratings">
      {BUTTONS.map(({ rating, label, mode }) => (
        <Button
          key={rating}
          size="l"
          mode={mode}
          stretched
          disabled={disabled}
          onClick={() => onRate(rating)}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
