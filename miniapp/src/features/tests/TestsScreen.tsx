import { Badge, Button, Caption, Cell, List, Placeholder, Section, Spinner, Text, Title } from '@telegram-apps/telegram-ui';
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../../api/client';
import type { StudentTest } from '../../api/types';
import { notify, useBackButton } from '../../lib/telegram';
import { firstGaps, isGap, QuestionText } from './QuestionText';
import '../grammar/grammar.css';
import './tests.css';

export const dayMonth = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });

const clock = (iso: string) => new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

/** «до 14:35» у контрольной на уроке, «до 5 марта» у домашнего теста. */
export const deadline = (t: { due: string; ends_at: string | null }) => `до ${t.ends_at ? clock(t.ends_at) : dayMonth(t.due)}`;

const minutesLeft = (ms: number) => {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

/**
 * Ученик: тесты от учителей его классов. openId — тест, открытый кнопкой
 * «Продолжить» или из сообщения бота: «Назад» из него сразу зовёт onExit.
 */
export function TestsScreen({ openId, onExit }: { openId: number | null; onExit?: () => void }) {
  const [tests, setTests] = useState<StudentTest[] | null>(null);
  const [open, setOpen] = useState<number | null>(openId);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);

  const close = useCallback(() => setOpen(null), []);
  useBackButton(open !== null && openId === null ? close : onExit ?? null);

  useEffect(() => {
    api.tests.list().then(setTests, (e: Error) => setError(e.message));
  }, [version]);

  if (error) return <Placeholder className="screen" header="Не открылось" description={error} />;
  if (!tests) return <div className="screen screen--center"><Spinner size="l" /></div>;

  const test = tests.find((t) => t.id === open);
  if (open !== null && !test) {
    return <Placeholder className="screen" header="Теста нет" description="Этого теста нет в твоих классах. Открой ссылку класса от учителя." />;
  }
  if (test) return <TestView key={test.id} test={test} onSubmitted={() => setVersion((v) => v + 1)} />;

  const todo = tests.filter((t) => !t.submitted_at && !t.closed);
  const rest = tests.filter((t) => t.submitted_at || t.closed);
  if (!tests.length) {
    return <Placeholder className="screen" header="Тестов пока нет" description="Когда учитель пришлёт тест, бот напишет тебе, а тест появится здесь." />;
  }
  return (
    <div className="screen screen--list">
      <List>
        {todo.length > 0 && (
          <Section header="Нужно сдать">
            {todo.map((t) => (
              <Cell key={t.id} multiline onClick={() => setOpen(t.id)} subtitle={`${t.teacher} · ${deadline(t)} · вопросов: ${t.questions.length}`}
                after={<Badge type="number" mode="critical">!</Badge>}>
                {t.title}
              </Cell>
            ))}
          </Section>
        )}
        {rest.length > 0 && (
          <Section header="Сданные и закрытые">
            {rest.map((t) => (
              <Cell key={t.id} multiline onClick={() => setOpen(t.id)} subtitle={`${t.teacher} · ${statusLine(t)}`}
                after={t.score !== null ? <Text>{t.score} / {t.total}</Text> : undefined}>
                {t.title}
              </Cell>
            ))}
          </Section>
        )}
      </List>
    </div>
  );
}

function statusLine(t: StudentTest): string {
  if (!t.submitted_at) return 'не сдан, срок прошёл';
  return t.closed ? 'результат готов' : `сдан, результат после ${t.ends_at ? clock(t.ends_at) : dayMonth(t.due)}`;
}

const DRAFT = (id: number) => `test-draft-${id}`;

function readDraft(id: number, total: number): string[] {
  try {
    const saved = JSON.parse(localStorage.getItem(DRAFT(id)) ?? '[]') as string[];
    return Array.from({ length: total }, (_, i) => saved[i] ?? '');
  } catch {
    // Черновик — удобство: битый или недоступный просто начинается заново.
    return Array(total).fill('');
  }
}

function TestView({ test, onSubmitted }: { test: StudentTest; onSubmitted: () => void }) {
  const [values, setValues] = useState(() => test.answers ?? readDraft(test.id, test.total));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const endsAt = test.ends_at ? Date.parse(test.ends_at) : null;
  const [left, setLeft] = useState(endsAt === null ? null : endsAt - Date.now());
  const autoSent = useRef(false);
  const warned = useRef(false);
  const running = !test.submitted_at && !test.closed;

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  function change(gap: number, value: string) {
    const next = values.map((v, i) => (i === gap ? value : v));
    setValues(next);
    try {
      localStorage.setItem(DRAFT(test.id), JSON.stringify(next));
    } catch {
      // Без хранилища (приватный режим) тест решается, просто без черновика.
    }
  }

  // Время вышло: пустое тоже сдаём, а потом перечитываем тест — откроются балл и ключ.
  useEffect(() => {
    if (left === null || test.closed) return;
    if (left <= 60_000 && left > 0 && running && !warned.current) {
      warned.current = true;
      notify('warning');
    }
    if (left > 0) return;
    if (!running) return onSubmitted();
    if (autoSent.current) return;
    autoSent.current = true;
    void send();
  }, [left]);

  useEffect(() => {
    if (endsAt === null || test.closed) return;
    const timer = setInterval(() => setLeft(endsAt - Date.now()), 1000);
    return () => clearInterval(timer);
  }, [endsAt, test.closed]);

  async function send() {
    setBusy(true);
    try {
      await api.tests.submit(test.id, values);
      notify('success');
      try {
        localStorage.removeItem(DRAFT(test.id));
      } catch {
        // Не удалился — останется лежать, тест всё равно сдан.
      }
      onSubmitted();
    } catch (e) {
      notify('error');
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="screen t-run">
      {running && left !== null && (
        <div className={`t-timer${left <= 60_000 ? ' t-timer--end' : ''}`}>⏱ Осталось {minutesLeft(left)}</div>
      )}
      <header className="t-head">
        <Title level="2" weight="1">{test.title}</Title>
        <Caption className="hint">{test.teacher} · {test.ends_at ? deadline(test) : `до ${dayMonth(test.due)} включительно`} · одна попытка</Caption>
      </header>
      {error && <div className="g-fb bad">{error}</div>}
      {running
        ? <Stepper test={test} values={values} onChange={change} busy={busy} onSend={send} />
        : <Results test={test} values={values} />}
    </div>
  );
}

function Results({ test, values }: { test: StudentTest; values: string[] }) {
  const firsts = firstGaps(test.questions);
  return (
    <>
      {test.score !== null && (
        <div className="g-result"><div className="g-big">{test.score} / {test.total}</div><Text className="hint">верных ответов</Text></div>
      )}
      {test.submitted_at && !test.closed && (
        <div className="g-fb ok">Тест сдан ✓ Результат и правильные ответы появятся после {test.ends_at ? clock(test.ends_at) : dayMonth(test.due)}.</div>
      )}
      {!test.submitted_at && test.closed && <div className="g-fb bad">Срок прошёл, тест не сдан.</div>}
      <section className="g-sheet">
        {test.questions.map((q, i) => (
          <div key={i} className="g-sent">
            <span className="g-num">{i + 1}.</span>
            <QuestionText question={q} first={firsts[i]!} values={values} marks={test.marks ?? undefined} />
          </div>
        ))}
      </section>
    </>
  );
}

interface StepperProps {
  test: StudentTest;
  values: string[];
  onChange: (gap: number, value: string) => void;
  busy: boolean;
  onSend: () => void;
}

/** Вопрос за вопросом; после последнего — сводка, где видно пустые. */
function Stepper({ test, values, onChange, busy, onSend }: StepperProps) {
  const count = test.questions.length;
  const [at, setAt] = useState(0);
  const sheet = useRef<HTMLElement>(null);
  const firsts = firstGaps(test.questions);
  const gapsOf = (i: number) => test.questions[i]!.parts.filter(isGap).length;
  const filled = (i: number) => values.slice(firsts[i], firsts[i]! + gapsOf(i)).every((v) => v.trim());
  const empty = test.questions.map((_, i) => i).filter((i) => !filled(i));
  const review = at === count;

  // Новый вопрос — курсор сразу в первый пропуск, клавиатура уже открыта.
  useEffect(() => {
    sheet.current?.querySelector('input')?.focus();
  }, [at]);

  function nextOnEnter(e: KeyboardEvent) {
    if (e.key !== 'Enter') return;
    const inputs = Array.from(sheet.current?.querySelectorAll('input') ?? []);
    const i = inputs.indexOf(e.target as HTMLInputElement);
    if (i >= 0 && i < inputs.length - 1) return inputs[i + 1]!.focus();
    setAt(at + 1);
  }

  return (
    <>
      <div className="t-dots">
        {test.questions.map((_, i) => (
          <button key={i} type="button" onClick={() => setAt(i)}
            className={`t-dot${i === at ? ' on' : ''}${filled(i) ? ' done' : ''}`}>{i + 1}</button>
        ))}
        <button type="button" onClick={() => setAt(count)} className={`t-dot t-dot--end${review ? ' on' : ''}`}>✓</button>
      </div>

      {review ? (
        <section className="g-sheet t-review">
          <Text weight="2">Заполнено {count - empty.length} из {count}</Text>
          {empty.length > 0
            ? <Caption className="hint">Пустые: {empty.map((i) => i + 1).join(', ')} — нажми номер сверху, чтобы вернуться. Пустой ответ засчитается как неверный.</Caption>
            : <Caption className="hint">Все вопросы заполнены. Изменить ответы после сдачи нельзя.</Caption>}
        </section>
      ) : (
        <section className="g-sheet t-one" ref={sheet} onKeyDown={nextOnEnter}>
          <Caption className="hint">Вопрос {at + 1} из {count}</Caption>
          <div className="g-sent">
            <QuestionText question={test.questions[at]!} first={firsts[at]!} values={values} onChange={onChange} />
          </div>
          <Caption className="hint">Можно сокращённо или полностью: don't = do not.</Caption>
        </section>
      )}

      <div className="g-bottom t-nav">
        <Button size="l" mode="bezeled" disabled={at === 0} onClick={() => setAt(at - 1)}>←</Button>
        {review
          ? <Button size="l" stretched mode="filled" loading={busy} onClick={onSend}>Сдать тест</Button>
          : <Button size="l" stretched mode="filled" onClick={() => setAt(at + 1)}>{at === count - 1 ? 'К сдаче' : 'Дальше →'}</Button>}
      </div>
    </>
  );
}
