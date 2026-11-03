import { useCallback, useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { GrammarAttempt, GrammarProgress } from '../../api/types';
import { markLegacyImported, readLegacyProgress } from '../../lib/telegram';
import { loadBook, type Book } from './book';

export interface Grammar {
  book: Book;
  progress: GrammarProgress;
  /** Итог задания: сразу в интерфейсе, следом на сервер. */
  save: (attempt: GrammarAttempt) => Promise<void>;
}

/**
 * Прогресс прежней тетради лежал в CloudStorage бота. При первом открытии
 * он переносится в базу — без этого ученик потерял бы сделанное, а учитель
 * не увидел бы его ошибок.
 */
async function importLegacy(): Promise<void> {
  try {
    const items = await readLegacyProgress();
    if (!Object.keys(items).length) return;
    await api.grammar.import(items);
    markLegacyImported();
  } catch (e) {
    // Перенос — бонус: если не вышло, тетрадь всё равно открывается,
    // а попытка повторится при следующем открытии.
    console.error('прогресс прежней тетради не перенесён:', e);
  }
}

export function useGrammar(): { data: Grammar | null; error: string } {
  const [book, setBook] = useState<Book | null>(null);
  const [progress, setProgress] = useState<GrammarProgress | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([loadBook(), importLegacy().then(() => api.grammar.progress())]).then(
      ([b, p]) => {
        setBook(b);
        setProgress(p);
      },
      (e: Error) => setError(e.message),
    );
  }, []);

  const save = useCallback(async (attempt: GrammarAttempt) => {
    setProgress((p) => {
      if (!p) return p;
      const before = p.results[attempt.item];
      return {
        ...p,
        results: {
          ...p.results,
          [attempt.item]: {
            clean: attempt.clean,
            was_wrong: !attempt.clean || !!before?.was_wrong,
            answers: attempt.answers,
          },
        },
      };
    });
    await api.grammar.attempt(attempt);
  }, []);

  return { data: book && progress ? { book, progress, save } : null, error };
}
