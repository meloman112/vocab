import { Badge, Button, Caption, Cell, List, Placeholder, Section, Spinner, Text, Title } from '@telegram-apps/telegram-ui';
import { useCallback, useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { StudentTest } from '../../api/types';
import { notify, useBackButton } from '../../lib/telegram';
import { firstGaps, QuestionText } from './QuestionText';
import '../grammar/grammar.css';
import './tests.css';

export const dayMonth = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });

/** Ученик: тесты от учителей его классов. openId — тест из сообщения бота. */
export function TestsScreen({ openId, onExit }: { openId: number | null; onExit: () => void }) {
  const [tests, setTests] = useState<StudentTest[] | null>(null);
  const [open, setOpen] = useState<number | null>(openId);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);

  const close = useCallback(() => setOpen(null), []);
  useBackButton(open !== null ? close : onExit);

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
              <Cell key={t.id} multiline onClick={() => setOpen(t.id)} subtitle={`${t.teacher} · до ${dayMonth(t.due)} · вопросов: ${t.questions.length}`}
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
  return t.closed ? 'результат готов' : `сдан, результат после ${dayMonth(t.due)}`;
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
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const firsts = firstGaps(test.questions);
  const running = !test.submitted_at && !test.closed;

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  function change(gap: number, value: string) {
    const next = values.map((v, i) => (i === gap ? value : v));
    setValues(next);
    setConfirm(false);
    try {
      localStorage.setItem(DRAFT(test.id), JSON.stringify(next));
    } catch {
      // Без хранилища (приватный режим) тест решается, просто без черновика.
    }
  }

  async function submit() {
    if (!confirm) return setConfirm(true);
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

  const empty = values.filter((v) => !v.trim()).length;
  return (
    <div className="screen t-run">
      <header className="t-head">
        <Title level="2" weight="1">{test.title}</Title>
        <Caption className="hint">{test.teacher} · до {dayMonth(test.due)} включительно · одна попытка</Caption>
      </header>
      {test.score !== null && (
        <div className="g-result"><div className="g-big">{test.score} / {test.total}</div><Text className="hint">верных ответов</Text></div>
      )}
      {test.submitted_at && !test.closed && (
        <div className="g-fb ok">Тест сдан ✓ Результат и правильные ответы появятся после {dayMonth(test.due)}.</div>
      )}
      {!test.submitted_at && test.closed && <div className="g-fb bad">Срок прошёл, тест не сдан.</div>}
      <section className="g-sheet">
        {running && <p className="g-task">Впиши ответы. Можно сокращённо или полностью: don't и do not — одно и то же.</p>}
        {test.questions.map((q, i) => (
          <div key={i} className="g-sent">
            <span className="g-num">{i + 1}.</span>
            <QuestionText question={q} first={firsts[i]!} values={values}
              onChange={running ? change : undefined} marks={running ? undefined : test.marks ?? undefined} />
          </div>
        ))}
      </section>
      {error && <div className="g-fb bad">{error}</div>}
      {running && (
        <div className="g-bottom">
          {confirm && <Caption className="t-confirm">{empty ? `Пустых ответов: ${empty}. ` : ''}Сдать? Изменить ответы потом будет нельзя.</Caption>}
          <Button size="l" stretched mode="filled" className="g-go" loading={busy} onClick={submit}>
            {confirm ? 'Да, сдать' : 'Сдать тест'}
          </Button>
        </div>
      )}
    </div>
  );
}
