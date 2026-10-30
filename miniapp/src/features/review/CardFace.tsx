import { Caption, LargeTitle, Text, Tappable } from '@telegram-apps/telegram-ui';
import { Fragment } from 'react';

import type { Card } from '../../api/types';

// «to book» и «a book» — разные карточки. На лицевой стороне без подсказки
// не понять, какую из них спрашивают. Артикль не ставим: «a water» хуже,
// чем подпись «существительное».
const POS_HINTS: Record<string, string> = {
  noun: 'существительное',
  adjective: 'прилагательное',
  adverb: 'наречие',
};

function title(card: Card): string {
  return card.homonym && card.pos === 'verb' ? `to ${card.word}` : card.word;
}

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
        {title(card)}
      </LargeTitle>

      {card.homonym && POS_HINTS[card.pos] && (
        <Caption className="card__ipa">{POS_HINTS[card.pos]}</Caption>
      )}

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
          {/* Fragment, а не div: перевод должен встать строкой ниже примера,
              а это делает flex-колонка .card__back только для прямых детей. */}
          {card.examples.map((example) => (
            <Fragment key={example.en}>
              <Text className="card__example">{example.en}</Text>
              <Caption className="card__example-ru">{example.ru}</Caption>
            </Fragment>
          ))}
          <Caption className="card__pos">
            ⭐ {card.top} · учат: {card.learners}
          </Caption>
        </div>
      )}
    </Tappable>
  );
}
