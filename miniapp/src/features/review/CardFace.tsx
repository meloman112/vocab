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
          <Caption className="card__pos">
            {card.pos}
            {card.irregular && ' · неправильное'}
          </Caption>
          {card.forms && <Caption className="card__pos">{card.forms}</Caption>}
          {card.examples.map((example) => (
            <div key={example.en}>
              <Text className="card__example">{example.en}</Text>
              <Caption className="card__example-ru">{example.ru}</Caption>
            </div>
          ))}
        </div>
      )}
    </Tappable>
  );
}
