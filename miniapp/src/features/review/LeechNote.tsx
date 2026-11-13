import { Button, Caption, Text } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import { api } from '../../api/client';
import type { Card } from '../../api/types';
import { notify } from '../../lib/telegram';

/** С этого числа провалов зубрёжка уже не помогает — нужна своя зацепка. */
const LEECH_LAPSES = 4;

/** Своя ассоциация к слову; у забываемого слова — просьба её придумать. */
export function LeechNote({ card }: { card: Card }) {
  const [note, setNote] = useState(card.note ?? '');
  const [saved, setSaved] = useState(card.note ?? '');

  if (saved) return <Text className="card__note">💡 {saved}</Text>;
  if (card.lapses < LEECH_LAPSES) return null;

  const save = () => {
    const text = note.trim();
    if (!text) return;
    api.note(card.id, text).then(
      () => {
        notify('success');
        setSaved(text);
      },
      (e: Error) => {
        notify('error');
        console.error('ассоциация не сохранилась:', e);
      },
    );
  };

  return (
    <div className="card__leech">
      <Caption>
        Слово забывалось {card.lapses} раз. Придумай свою зацепку: созвучие, картинку или фразу про себя.
      </Caption>
      <textarea value={note} maxLength={300} rows={2} placeholder="postpone — «пост» после понедельника: отложу"
        onChange={(e) => setNote(e.target.value)} />
      <Button size="s" mode="bezeled" disabled={!note.trim()} onClick={save}>Запомнить зацепку</Button>
    </div>
  );
}
