import { Button, Caption, Text } from '@telegram-apps/telegram-ui';

import type { QuizCard, Rating } from '../../api/types';
import { title } from '../../lib/word';
import { ReportButton } from '../report/ReportButton';
import { ALMOST, RIGHT } from './check';

interface Props {
  card: QuizCard;
  rating: Rating;
  note?: string;
  onNext: () => void;
}

const VERDICT: Record<number, string> = { [RIGHT]: '✅ Верно', [ALMOST]: '🟡 Почти' };

/** Разбор после ответа: что было правильно, пример и «Дальше». */
export function Feedback({ card, rating, note, onNext }: Props) {
  const example = card.examples[0];
  return (
    <div className="feedback">
      <Text weight="2" className={`verdict verdict--${rating}`}>
        {VERDICT[rating] ?? '❌ Неверно'}
        {note && ` — ${note}`}
      </Text>
      <Text>
        <b>{title(card)}</b> — {card.translation}
      </Text>
      {card.forms && <Caption className="hint">{card.forms}</Caption>}
      {example && (
        <Caption className="hint">
          {example.en} — {example.ru}
        </Caption>
      )}
      <ReportButton wordId={card.word_id} />
      <Button size="l" stretched onClick={onNext} autoFocus>
        Дальше
      </Button>
    </div>
  );
}
