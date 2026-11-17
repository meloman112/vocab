import { Badge, Button, Caption, Cell, List, Section, Text, Title } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import type { Stats } from '../../api/types';
import { MODES, modeById, type Mode, type ModeId } from '../quiz/modes';

/** «Учить» — главная кнопка, глаголы — отдельной строкой; остальное свёрнуто. */
const REST = MODES.filter((m) => m.id !== 'learn' && m.id !== 'irregular');

interface Props {
  stats: Stats | null;
  error: string;
  onCards: () => void;
  onDeck: (deck: string) => void;
  onQuiz: (mode: ModeId) => void;
}

export function WordsScreen({ stats, error, onCards, onDeck, onQuiz }: Props) {
  const [all, setAll] = useState(false);
  const due = stats?.due_now ?? 0;
  const modeCell = (mode: Mode) => (
    <Cell key={mode.id} before={<Icon>{mode.icon}</Icon>} subtitle={mode.subtitle} onClick={() => onQuiz(mode.id)}>
      {mode.title}
    </Cell>
  );

  return (
    <div className="screen screen--list">
      <header className="tab-head">
        <Title level="1" weight="1">Слова</Title>
        {stats && <Text className="hint">🔥 Серия: {stats.streak} дн. · рекорд {stats.best_streak}</Text>}
        <Button size="l" stretched onClick={() => onQuiz('learn')}>
          Учить
        </Button>
        <Caption className="hint tab-head__next">{modeById('learn').subtitle}</Caption>
        {error && <Caption className="error">Цифры не загрузились: {error}</Caption>}
      </header>

      <List>
        <Section>
          <Cell
            before={<Icon>🧠</Icon>}
            subtitle={due > 0 ? `Ждут повторения: ${due}` : 'Новые слова из общего словаря'}
            after={due > 0 ? <Badge type="number">{due}</Badge> : undefined}
            onClick={onCards}
          >
            Карточки
          </Cell>
          {/* Тап — следующие 10 слов набора в свои карточки, сразу на изучение. */}
          {stats?.decks.map((deck) => (
            <Cell
              key={deck.deck}
              before={<Icon>📘</Icon>}
              subtitle={`Изучено ${deck.learned} из ${deck.total} · учить следующие 10`}
              multiline
              onClick={() => onDeck(deck.deck)}
            >
              {deck.deck}
            </Cell>
          ))}
          {modeCell(modeById('irregular'))}
        </Section>

        <Section footer="Ответ в тренировке засчитывается как повторение: ошибся — слово вернётся скорее.">
          <Cell before={<Icon>⋯</Icon>} after={<Text className="hint">{all ? '▴' : '▾'}</Text>} onClick={() => setAll(!all)}>
            Все тренировки
          </Cell>
          {all && REST.map(modeCell)}
        </Section>
      </List>
    </div>
  );
}

function Icon({ children }: { children: string }) {
  return <Text className="icon">{children}</Text>;
}
