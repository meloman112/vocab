import { Caption, Progress } from '@telegram-apps/telegram-ui';

import type { Card, Rating } from '../../api/types';
import { CardFace } from './CardFace';
import { RatingBar } from './RatingBar';

interface Props {
  card: Card;
  index: number;
  total: number;
  flipped: boolean;
  onFlip: () => void;
  onRate: (rating: Rating) => void;
}

export function ReviewScreen({ card, index, total, flipped, onFlip, onRate }: Props) {
  return (
    <div className="screen">
      <header className="screen__head">
        <Progress value={(index / total) * 100} />
        <Caption className="screen__counter">
          {index + 1}/{total}
        </Caption>
      </header>

      <main className="screen__body">
        <CardFace card={card} flipped={flipped} onFlip={onFlip} />
      </main>

      <footer className="screen__foot">
        {/* Оценивать можно только перевёрнутую карточку: иначе оценка
            «Good» ставится вслепую и портит расписание. */}
        <RatingBar disabled={!flipped} onRate={onRate} />
      </footer>
    </div>
  );
}
