import { Button, Cell, Input, List, Placeholder, Section, Spinner } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { SchoolClass, TestRow } from '../../api/types';
import { notify, shareLink } from '../../lib/telegram';
import { plural } from '../teacher/format';
import { dayMonth } from './TestsScreen';

/** Вкладка «Тесты» у учителя: классы со ссылками и отправленные тесты. */
export function TeacherTests({ onNew, onOpen }: { onNew: () => void; onOpen: (id: number) => void }) {
  const [classes, setClasses] = useState<SchoolClass[] | null>(null);
  const [tests, setTests] = useState<TestRow[] | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.teacher.classes(), api.teacher.tests()]).then(([c, t]) => {
      setClasses(c);
      setTests(t);
    }, (e: Error) => setError(e.message));
  }, []);

  async function createClass() {
    setBusy(true);
    try {
      const created = await api.teacher.createClass(name.trim());
      notify('success');
      setClasses((list) => [...(list ?? []), created]);
      setName('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Placeholder header="Не открылось" description={error} />;
  if (!classes || !tests) return <div className="screen--center"><Spinner size="l" /></div>;

  return (
    <List>
      <Section header="Тесты">
        <Cell multiline onClick={onNew} disabled={!classes.length} before={<span className="icon">➕</span>}
          subtitle={classes.length ? 'Вопросы с пропуском или готовая контрольная' : 'Сначала создай класс ниже'}>
          Новый тест
        </Cell>
        {tests.map((t) => (
          <Cell key={t.id} multiline onClick={() => onOpen(t.id)}
            subtitle={`${t.class_name} · ${t.closed ? 'срок прошёл' : `до ${dayMonth(t.due)}`} · сдали ${t.submitted} из ${t.members}`}>
            {t.title}
          </Cell>
        ))}
      </Section>

      <Section header="Классы"
        footer="Ученик открывает ссылку класса — бот добавляет его в класс. Тесты приходят всем ученикам класса.">
        {classes.map((c) => (
          <Cell key={c.id} multiline onClick={() => shareLink(c.link, `Заходи в класс «${c.name}»: сюда будут приходить тесты`)}
            subtitle={<>{c.members} {plural(c.members, 'ученик', 'ученика', 'учеников')} · нажми, чтобы переслать ссылку<div className="t-link">{c.link}</div></>}>
            {c.name}
          </Cell>
        ))}
        <Input value={name} placeholder="Новый класс, например 9А" maxLength={60} onChange={(e) => setName(e.target.value)} />
        <div className="t-format">
          <Button size="m" mode="bezeled" disabled={!name.trim() || busy} loading={busy} onClick={createClass}>
            Создать класс
          </Button>
        </div>
      </Section>
    </List>
  );
}
