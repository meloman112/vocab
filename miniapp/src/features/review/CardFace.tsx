import { Caption, LargeTitle, Text, Tappable } from '@telegram-apps/telegram-ui';

import type { Card } from '../../api/types';

interface Props {
  card: Card;
  flipped: boolean;
  onFlip: () => void;
}

export function CardFace({ card, flipped, onFlip }: Props) {
  return (
    <Tappable
      className="card"
      Component="div"
      // Тап по всей карточке, а не по кнопке «показать»: палец на телефоне
      // попадает по площади, а не по цели в 40 пикселей.
      onClick={flipped ? undefined : onFlip}
      interactiveAnimation="opacity"
    >
      <LargeTitle weight="1" className="card__word">
        {card.word}
      </LargeTitle>

      {card.ipa && <Caption className="card__ipa">/{card.ipa}/</Caption>}

      {!flipped && <Caption className="card__hint">нажми, чтобы проверить</Caption>}

      {flipped && (
        <div className="card__back">
          <Text weight="2">{card.translation}</Text>
          {card.pos && <Caption className="card__pos">{card.pos}</Caption>}
          {card.example && <Text className="card__example">{card.example}</Text>}
          {card.example_ru && (
            <Caption className="card__example-ru">{card.example_ru}</Caption>
          )}
        </div>
      )}
    </Tappable>
  );
}
