import { Button, Cell, List, Placeholder, Section, Spinner, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import { type AdminWord, REPORT_REASONS, type ReportedWord } from '../../api/types';
import { notify } from '../../lib/telegram';

interface Props {
  version: number;
  onEdit: (word: AdminWord) => void;
  onChanged: () => void;
}

export function ReportsTab({ version, onEdit, onChanged }: Props) {
  const [words, setWords] = useState<ReportedWord[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    api.admin.reports().then(setWords, (e: Error) => setError(e.message));
  }, [version]);

  const act = (word: ReportedWord, action: () => Promise<unknown>) => {
    setBusy(word.id);
    action().then(
      () => {
        notify('success');
        onChanged();
      },
      (e: Error) => {
        notify('error');
        setError(e.message);
      },
    ).finally(() => setBusy(null));
  };

  if (error) return <Placeholder header="Ошибка" description={error} />;
  if (!words) return <Spinner size="m" className="center" />;
  if (words.length === 0) return <Placeholder header="Жалоб нет" description="Словарь в порядке." />;

  return (
    <List>
      {words.map((word) => (
        <Section key={word.id} header={`${word.lemma} · ${word.pos}${word.banned ? ' · в бане' : ''}`}>
          <Cell
            multiline
            subtitle={word.reasons.map((r) => REPORT_REASONS[r]).join(', ')}
            description={word.comments.length > 0 ? word.comments.map((c) => `«${c}»`).join(' ') : undefined}
            after={<Text>×{word.reports}</Text>}
          >
            {word.translation}
          </Cell>
          <div className="admin__actions">
            <Button size="s" mode="bezeled" onClick={() => onEdit(word)} disabled={busy === word.id}>
              Править
            </Button>
            <Button
              size="s"
              mode="gray"
              disabled={busy === word.id || word.banned}
              onClick={() => act(word, () => api.admin.save(word.id, { ...editable(word), banned: true }))}
            >
              В бан
            </Button>
            <Button
              size="s"
              mode="plain"
              disabled={busy === word.id}
              onClick={() => act(word, () => api.admin.dismiss(word.id))}
            >
              Отклонить
            </Button>
          </div>
        </Section>
      ))}
    </List>
  );
}

function editable(word: AdminWord) {
  const { translation, ipa, forms, irregular, examples, level, banned } = word;
  return { translation, ipa, forms, irregular, examples, level, banned };
}
