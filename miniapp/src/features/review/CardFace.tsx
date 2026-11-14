import { Caption, LargeTitle, Text, Tappable } from '@telegram-apps/telegram-ui';
import { Fragment } from 'react';

import type { Card } from '../../api/types';
import { canSpeak, speak } from '../../lib/speech';
import { irregularPattern, POS_HINTS, title } from '../../lib/word';
import { ReportButton } from '../report/ReportButton';
import { LeechNote } from './LeechNote';

interface Props {
  card: Card;
  flipped: boolean;
  onFlip: () => void;
}

export function CardFace({ card, flipped, onFlip }: Props) {
  const pattern = card.irregular && card.pos === 'verb' ? irregularPattern(card.forms) : null;
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

      {/* Динамик в строке транскрипции, а не отдельно по центру: туда
          приходится тап «перевернуть», и он озвучивал бы слово. */}
      <Caption className="card__ipa">
        {card.ipa && `/${card.ipa}/ `}
        {canSpeak && (
          <button
            type="button"
            className="link"
            aria-label="Произнести"
            onClick={(event) => {
              event.stopPropagation();
              speak(card.word);
            }}
          >
            🔊
          </button>
        )}
      </Caption>

      {/* Вспомнить формы до переворота — то же активное припоминание, что и перевод. */}
      {!flipped && (
        <Caption className="card__hint">
          {pattern ? 'вспомни перевод и три формы, потом нажми' : 'нажми, чтобы проверить'}
        </Caption>
      )}

      {flipped && (
        <div className="card__back">
          <Text weight="2">{card.translation}</Text>
          <Caption className="card__pos">
            {card.pos}
            {card.irregular && ' · неправильное'}
          </Caption>
          {pattern ? (
            <>
              <Text weight="2">
                {card.forms}{' '}
                {canSpeak && (
                  <button
                    type="button"
                    className="link"
                    aria-label="Произнести формы"
                    onClick={(event) => {
                      event.stopPropagation();
                      // go, went, gone — ритм тройки запоминается на слух.
                      speak(card.forms.replace(/[·/]/g, ','));
                    }}
                  >
                    🔊
                  </button>
                )}
              </Text>
              <Caption className="card__pos">{pattern}</Caption>
            </>
          ) : (
            card.forms && <Caption className="card__pos">{card.forms}</Caption>
          )}
          {/* Fragment, а не div: перевод должен встать строкой ниже примера,
              а это делает flex-колонка .card__back только для прямых детей. */}
          {card.examples.map((example) => (
            <Fragment key={example.en}>
              <Text className="card__example">{example.en}</Text>
              <Caption className="card__example-ru">{example.ru}</Caption>
            </Fragment>
          ))}
          {card.contrast?.others.length ? (
            <Caption className="card__pos">
              ⚖️ Не путай: {card.contrast.others.map((o) => `${o.word} — ${o.note}`).join('; ')}
            </Caption>
          ) : null}
          {card.contrast?.collocations.length ? (
            <Caption className="card__pos">🔗 {card.contrast.collocations.join(' · ')}</Caption>
          ) : null}
          <LeechNote key={card.id} card={card} />
          <Caption className="card__pos">
            ⭐ {card.top} · учат: {card.learners}
          </Caption>
          {card.deck && (
            <Caption className="card__pos">
              📘 {card.deck}
              {card.topic && ` · ${card.topic}`}
            </Caption>
          )}
          <ReportButton wordId={card.word_id} />
        </div>
      )}
    </Tappable>
  );
}
