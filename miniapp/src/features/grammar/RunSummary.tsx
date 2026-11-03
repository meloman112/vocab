import { Button, Caption, Title } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import { api } from '../../api/client';
import { filled, pdfExercises } from './book';
import type { RunProps } from './ExerciseRun';

/** Итоги захода: сколько с первого раза, где были ошибки — с правильными ответами. */
export function RunSummary({ grammar, keys, title, review, onHome, onMistakes, onMix, toast }: RunProps) {
  const { book, progress } = grammar;
  const [sending, setSending] = useState(false);
  const results = progress.results;
  const clean = keys.filter((k) => results[k]?.clean).length;
  const wrong = keys.filter((k) => results[k] && !results[k].clean);
  const anyMistakes = Object.values(results).some((r) => !r.clean);
  const exIds = [...new Set(keys.map((k) => book.items.get(k)!.ex))];

  async function sendPdf() {
    setSending(true);
    try {
      await api.grammar.pdf(pdfExercises(book, exIds, results));
      toast('PDF отправлен в чат с ботом');
    } catch (e) {
      toast(`PDF не отправлен: ${(e as Error).message}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="screen g-summary">
      <div className="g-result">
        <Caption className="hint">{title} · итоги</Caption>
        <div className="g-big">
          {clean}/{keys.length}
        </div>
        <Caption className="hint">с первого раза</Caption>
      </div>

      {wrong.length > 0 && (
        <>
          <Title level="3" weight="2">
            Где была ошибка
          </Title>
          <div className="g-mistakes">
            {wrong.map((k) => (
              <div key={k} className="g-mistake">
                <span className="g-num">
                  {book.items.get(k)!.ex}.{book.items.get(k)!.n}
                </span>
                {filled(book, k).map((p, i) => (p.answer ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="actions g-actions">
        {!review && (
          <Button size="l" mode="bezeled" stretched loading={sending} onClick={sendPdf}>
            Отправить PDF в чат
          </Button>
        )}
        {anyMistakes ? (
          <Button size="l" mode="bezeled" stretched onClick={onMistakes}>
            Работа над ошибками
          </Button>
        ) : (
          <Button size="l" mode="bezeled" stretched onClick={onMix}>
            Ещё вперемешку
          </Button>
        )}
        <Button size="l" stretched onClick={onHome}>
          К упражнениям
        </Button>
      </div>
    </div>
  );
}
