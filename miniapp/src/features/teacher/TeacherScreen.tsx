import { Badge, Caption, Cell, List, Placeholder, Section, SegmentedControl, Spinner } from '@telegram-apps/telegram-ui';
import { useCallback, useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { CommonMistake, Student } from '../../api/types';
import { useBackButton } from '../../lib/telegram';
import { loadBook, type Book } from '../grammar/book';
import { ago, plural } from './format';
import { Sentence } from './Sentence';
import { StudentView } from './StudentView';
import '../grammar/grammar.css';

type Tab = 'students' | 'common';

/** Учитель: кто как сделал тетрадь и где ошибается класс. */
export function TeacherScreen({ onExit }: { onExit: () => void }) {
  const [tab, setTab] = useState<Tab>('students');
  const [book, setBook] = useState<Book | null>(null);
  const [students, setStudents] = useState<Student[] | null>(null);
  const [common, setCommon] = useState<CommonMistake[] | null>(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<Student | null>(null);
  // Засчитали ответ в карточке ученика — списки надо перечитать.
  const [version, setVersion] = useState(0);

  const close = useCallback(() => setOpen(null), []);
  useBackButton(open ? close : onExit);

  useEffect(() => {
    Promise.all([loadBook(), api.teacher.students(), api.teacher.common()]).then(
      ([b, s, c]) => {
        setBook(b);
        setStudents(s);
        setCommon(c);
      },
      (e: Error) => setError(e.message),
    );
  }, [version]);

  useEffect(() => window.scrollTo(0, 0), [open, tab]);

  if (error) return <Placeholder className="screen" header="Не открылось" description={error} />;
  if (!book || !students || !common) {
    return (
      <div className="screen screen--center">
        <Spinner size="l" />
      </div>
    );
  }

  if (open) return <StudentView book={book} student={open} onChanged={() => setVersion((v) => v + 1)} />;

  const unresolved = students.reduce((n, s) => n + s.mistakes, 0);

  return (
    <div className="screen screen--list">
      <Caption className="hint admin__summary">
        Учеников: {students.length} · неразобранных ошибок: {unresolved}
      </Caption>
      <SegmentedControl>
        <SegmentedControl.Item selected={tab === 'students'} onClick={() => setTab('students')}>
          Ученики
        </SegmentedControl.Item>
        <SegmentedControl.Item selected={tab === 'common'} onClick={() => setTab('common')}>
          Частые ошибки
        </SegmentedControl.Item>
      </SegmentedControl>

      {tab === 'students' ? (
        students.length ? (
          <List>
            <Section footer="Сверху — кто занимался последним. Красное число — ошибки, которые ты ещё не разобрал.">
              {students.map((s) => (
                <Cell key={s.user_id} onClick={() => setOpen(s)} multiline
                  subtitle={`Сделано ${s.done} · с первого раза ${s.first_try}${s.last_at ? ` · ${ago(s.last_at)}` : ''}`}
                  after={s.mistakes > 0 ? <Badge type="number" mode="critical">{s.mistakes}</Badge> : <span className="g-check">✓</span>}>
                  {s.name}
                </Cell>
              ))}
            </Section>
          </List>
        ) : (
          <Placeholder header="Пока пусто" description="Здесь появятся ученики, как только кто-нибудь решит задание в тетради." />
        )
      ) : common.length ? (
        <List>
          <Section footer="Задания, на которых ошибается больше всего учеников. Ответы — последние неверные.">
            {common.map((c) => (
              <div key={c.item} className="g-common">
                <Caption className="hint">
                  Упр. {c.item.split('-')[0]} · ошиблись {c.students} {plural(c.students, 'ученик', 'ученика', 'учеников')}
                </Caption>
                <Sentence book={book} itemKey={c.item} />
                <div className="g-wrong-list">
                  {[...new Set(c.answers)].map((a) => (
                    <s key={a} className="g-wrong">{a}</s>
                  ))}
                </div>
              </div>
            ))}
          </Section>
        </List>
      ) : (
        <Placeholder header="Ошибок нет" description="Ни одной неразобранной ошибки в классе." />
      )}
    </div>
  );
}
