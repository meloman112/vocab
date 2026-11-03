import { Button, Caption, Placeholder, SegmentedControl, Spinner, Text, Title } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { Student, StudentDetail, StudentMistake } from '../../api/types';
import { notify } from '../../lib/telegram';
import { slotsOf, type Book } from '../grammar/book';
import { bracketLabel } from '../grammar/engine';
import { ago } from './format';
import { Sentence } from './Sentence';

type Filter = 'open' | 'all';

interface Props {
  book: Book;
  student: Student;
  onChanged: () => void;
}

/**
 * Ошибки ученика по заданиям: что он ввёл, почему это не так и чем всё
 * кончилось. «Засчитать» — для верного ответа, которого не знал ключ.
 */
export function StudentView({ book, student, onChanged }: Props) {
  const [detail, setDetail] = useState<StudentDetail | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('open');
  const [busy, setBusy] = useState<number | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api.teacher.student(student.user_id).then(setDetail, (e: Error) => setError(e.message));
  }, [student.user_id, version]);

  async function accept(m: StudentMistake) {
    setBusy(m.id);
    try {
      await api.teacher.accept(m.id);
      notify('success');
      setVersion((v) => v + 1);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (error) return <Placeholder className="screen" header="Не открылось" description={error} />;
  if (!detail) {
    return (
      <div className="screen screen--center">
        <Spinner size="l" />
      </div>
    );
  }

  const results = new Map(detail.results.map((r) => [r.item, r]));
  const shown = detail.mistakes.filter((m) => filter === 'all' || !m.accepted);
  // Группы по заданию в порядке последней ошибки: свежее — сверху.
  const groups = new Map<string, StudentMistake[]>();
  for (const m of shown) groups.set(m.item, [...(groups.get(m.item) ?? []), m]);
  const firstTry = detail.results.filter((r) => r.clean && !r.was_wrong).length;
  const exercises = new Set(detail.results.map((r) => r.item.split('-')[0])).size;

  return (
    <div className="screen g-student">
      <header>
        <Title level="2" weight="1">
          {detail.name}
        </Title>
        <Text className="hint">
          Заданий: {detail.results.length} в {exercises} упр. · с первого раза {firstTry} · сейчас с ошибкой{' '}
          {detail.results.filter((r) => !r.clean).length}
        </Text>
      </header>

      <SegmentedControl>
        <SegmentedControl.Item selected={filter === 'open'} onClick={() => setFilter('open')}>
          Неразобранные
        </SegmentedControl.Item>
        <SegmentedControl.Item selected={filter === 'all'} onClick={() => setFilter('all')}>
          Все ошибки
        </SegmentedControl.Item>
      </SegmentedControl>

      {groups.size === 0 && (
        <Placeholder header={filter === 'open' ? 'Всё разобрано' : 'Ошибок нет'}
          description={filter === 'open' ? 'Неразобранных ошибок у ученика нет.' : 'Ученик ещё ни разу не ошибся.'} />
      )}

      {[...groups].map(([item, mistakes]) => {
        const r = results.get(item);
        const slots = book.items.has(item) ? slotsOf(book, item) : [];
        return (
          <section key={item} className="g-card">
            <Caption className="hint">
              {r ? (r.clean ? '✅ Исправлено' : '❗ Пока с ошибкой') : 'Не закончено'}
              {r && ` · ${ago(r.updated_at)}`}
            </Caption>
            <Sentence book={book} itemKey={item} />
            {mistakes.map((m) => (
              <div key={m.id} className="g-attempt">
                <div>
                  {slots.length > 1 && <small className="hint">{bracketLabel(slots[m.slot]!) || `пропуск ${m.slot + 1}`}: </small>}
                  <s className="g-wrong">{m.answer}</s>
                  {m.why && <div className="g-attempt-why">{m.why}</div>}
                </div>
                {m.accepted ? (
                  <span className="g-accepted">✓ засчитано</span>
                ) : (
                  <Button size="s" mode="bezeled" loading={busy === m.id} onClick={() => accept(m)}>
                    Засчитать
                  </Button>
                )}
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
