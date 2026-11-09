import { Button, Caption, Cell, List, Placeholder, Section, SegmentedControl, Spinner, Text, Title } from '@telegram-apps/telegram-ui';
import { type ReactNode, useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { StudentScore, TestReport as Report } from '../../api/types';
import { notify } from '../../lib/telegram';
import { firstGaps, isGap, QuestionText } from './QuestionText';
import { dayMonth } from './TestsScreen';

type Tab = 'questions' | 'students';

/** Учитель: кто сдал, где ошибся класс, и «Засчитать» для верного ответа, которого не знал ключ. */
export function TestReport({ id, onDeleted }: { id: number; onDeleted: () => void }) {
  const [report, setReport] = useState<Report | null>(null);
  const [tab, setTab] = useState<Tab>('questions');
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api.teacher.test(id).then(setReport, (e: Error) => setError(e.message));
  }, [id, version]);

  async function act(key: string, call: () => Promise<void>, after: () => void) {
    setBusy(key);
    try {
      await call();
      notify('success');
      after();
    } catch (e) {
      notify('error');
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }

  if (error) return <Placeholder className="screen" header="Не получилось" description={error} />;
  if (!report) return <div className="screen screen--center"><Spinner size="l" /></div>;

  const done = report.students.filter((s) => s.score !== null);
  const total = report.gaps.length;
  const avg = done.length ? Math.round((done.reduce((n, s) => n + s.score!, 0) / done.length / total) * 100) : null;
  const firsts = firstGaps(report.questions);
  const multi = report.questions.map((q) => q.parts.filter(isGap).length > 1);

  return (
    <div className="screen screen--list">
      <header className="t-head">
        <Title level="2" weight="1">{report.title}</Title>
        <Caption className="hint">
          {report.class_name} · {report.closed ? 'срок прошёл' : `до ${dayMonth(report.due)}`} · сдали {done.length} из {report.students.length}
          {avg !== null && ` · средний балл ${avg}%`}
        </Caption>
      </header>
      <SegmentedControl>
        <SegmentedControl.Item selected={tab === 'questions'} onClick={() => setTab('questions')}>По вопросам</SegmentedControl.Item>
        <SegmentedControl.Item selected={tab === 'students'} onClick={() => setTab('students')}>По ученикам</SegmentedControl.Item>
      </SegmentedControl>

      {tab === 'questions' ? (
        <List>
          <Section footer="«Засчитать» — ответ верный, а ключ его не знал. Балл пересчитается у всех, кто так ответил.">
            {report.gaps.map((g) => {
              const pct = done.length ? Math.round((g.correct / done.length) * 100) : 0;
              const showSentence = g.gap === firsts[g.question];
              return (
                <div key={g.gap} className="g-common">
                  {showSentence && (
                    <div className="g-mistake"><span className="g-num">{g.question + 1}.</span><QuestionText question={report.questions[g.question]!} first={firsts[g.question]!} /></div>
                  )}
                  {multi[g.question] && <Caption className="hint">Пропуск {g.gap - firsts[g.question]! + 1}</Caption>}
                  <div className="t-stat"><span>верно {g.correct} из {done.length}</span><span>{pct}%</span></div>
                  <div className="t-meter"><i className={pct >= 75 ? '' : pct >= 50 ? 'warn' : 'bad'} style={{ width: `${pct}%` }} /></div>
                  {g.wrong.map((w) => (
                    <div key={w.answer} className="g-attempt">
                      <div><s className="g-wrong">{w.answer || 'пусто'}</s> <span className="hint">× {w.count}</span></div>
                      {w.answer && (
                        <Button size="s" mode="bezeled" loading={busy === `${g.gap}:${w.answer}`}
                          onClick={() => act(`${g.gap}:${w.answer}`, () => api.teacher.acceptAnswer(report.id, g.gap, w.answer), () => setVersion((v) => v + 1))}>
                          Засчитать
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}
          </Section>
        </List>
      ) : (
        <List>
          <Section footer="Нажми на ученика, чтобы увидеть его ответы.">
            {report.students.map((s) => (
              <StudentRow key={s.user_id} s={s} total={total} open={open === s.user_id}
                onToggle={() => setOpen(open === s.user_id ? null : s.user_id)}>
                <div className="g-sheet t-preview">
                  {report.questions.map((q, i) => (
                    <div key={i} className="g-sent"><span className="g-num">{i + 1}.</span>
                      <QuestionText question={q} first={firsts[i]!} values={s.answers ?? []} marks={s.marks} /></div>
                  ))}
                </div>
              </StudentRow>
            ))}
          </Section>
        </List>
      )}

      <div className="bottom">
        {confirmDelete && <Caption className="t-confirm">Тест и ответы учеников удалятся насовсем.</Caption>}
        <Button size="m" mode="plain" stretched loading={busy === 'delete'}
          onClick={() => (confirmDelete ? act('delete', () => api.teacher.deleteTest(report.id), onDeleted) : setConfirmDelete(true))}>
          {confirmDelete ? 'Да, удалить тест' : 'Удалить тест'}
        </Button>
      </div>
    </div>
  );
}

function StudentRow({ s, total, open, onToggle, children }:
  { s: StudentScore; total: number; open: boolean; onToggle: () => void; children: ReactNode }) {
  if (s.score === null) {
    return <Cell subtitle="не сдал" after={<Text className="hint">—</Text>}>{s.name}</Cell>;
  }
  const pct = s.score / total;
  return (
    <>
      <Cell onClick={onToggle} subtitle={`сдал ${new Date(s.submitted_at!).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`}
        after={<Text weight="2" className={pct >= 0.75 ? 't-good' : pct >= 0.5 ? 't-mid' : 't-poor'}>{s.score} / {total}</Text>}>
        {s.name}
      </Cell>
      {open && children}
    </>
  );
}
