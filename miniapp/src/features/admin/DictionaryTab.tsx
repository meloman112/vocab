import { Cell, Input, List, Placeholder, Section, Spinner, Text } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { AdminWord } from '../../api/types';

const DEBOUNCE_MS = 300;

interface Props {
  version: number;
  onEdit: (word: AdminWord) => void;
}

/** Поиск по всему общему словарю, вместе с заблокированными. */
export function DictionaryTab({ version, onEdit }: Props) {
  const [query, setQuery] = useState('');
  const [words, setWords] = useState<AdminWord[] | null>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setWords([]);
      return;
    }
    setWords(null);
    // Ответ на устаревший запрос не должен перезаписать свежий.
    let stale = false;
    const timer = window.setTimeout(() => {
      api.admin.words(q).then(
        (found) => !stale && setWords(found),
        (e: Error) => !stale && setError(e.message),
      );
    }, DEBOUNCE_MS);
    return () => {
      stale = true;
      window.clearTimeout(timer);
    };
  }, [query, version]);

  return (
    <>
      <Input
        placeholder="Найти слово"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
      />
      {error && <Placeholder header="Ошибка" description={error} />}
      {words === null && <Spinner size="m" className="center" />}
      {words && words.length > 0 && (
        <List>
          <Section>
            {words.map((word) => (
              <Cell
                key={word.id}
                subtitle={word.translation}
                after={<Text>{word.banned ? '🚫' : word.level}</Text>}
                onClick={() => onEdit(word)}
              >
                {word.lemma} <span className="hint">· {word.pos}</span>
              </Cell>
            ))}
          </Section>
        </List>
      )}
      {words && words.length === 0 && query.trim() && <Placeholder description="Ничего не нашлось" />}
    </>
  );
}
