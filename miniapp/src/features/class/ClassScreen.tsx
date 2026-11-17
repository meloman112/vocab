import { Badge, Button, Cell, List, Placeholder, Section, Spinner } from '@telegram-apps/telegram-ui';
import { useCallback, useState } from 'react';

import type { Me, StudentTest } from '../../api/types';
import { useBackButton, useHasBack } from '../../lib/telegram';
import { TeacherScreen } from '../teacher/TeacherScreen';
import { CreateClass } from '../tests/TeacherTests';
import { TestsScreen } from '../tests/TestsScreen';

interface Props {
  me: Me | null;
  tests: StudentTest[] | null;
  error: string;
  /** Открыли кнопкой бота «Тесты»: и учителю сразу показываем тесты, которые сдаёт он сам. */
  startTests: boolean;
  /** Создан первый класс — пользователь стал учителем, /me надо перечитать. */
  onChanged: () => void;
}

/** Ученику — тесты от учителя, учителю — ученики, классы и его тесты. */
export function ClassScreen({ me, tests, error, startTests, onChanged }: Props) {
  const [ownTests, setOwnTests] = useState(startTests);
  const [form, setForm] = useState(false);
  const hasBack = useHasBack();
  const closeOwnTests = useCallback(() => setOwnTests(false), []);
  const closeForm = useCallback(() => setForm(false), []);
  useBackButton(form && me && !me.is_teacher ? closeForm : null);

  if (ownTests) return <TestsScreen openId={null} onExit={me?.is_teacher ? closeOwnTests : undefined} />;
  if (!me || !tests) {
    if (error) return <Placeholder className="screen" header="Не открылось" description={error} />;
    return <div className="screen screen--center"><Spinner size="l" /></div>;
  }

  if (me.is_teacher) {
    const todo = tests.filter((t) => !t.submitted_at && !t.closed).length;
    return (
      <>
        {/* Учитель бывает и учеником; внутри карточки ученика или теста строка лишняя. */}
        {tests.length > 0 && !hasBack && (
          <List>
            <Section>
              <Cell before={<span className="icon">📝</span>} onClick={() => setOwnTests(true)}
                after={todo ? <Badge type="number" mode="critical">{todo}</Badge> : undefined}>
                Тесты от учителя
              </Cell>
            </Section>
          </List>
        )}
        {/* После первого класса — сразу к нему: там ссылка для учеников. */}
        <TeacherScreen startTab={form ? 'tests' : 'students'} />
      </>
    );
  }

  if (me.in_class || tests.length) return <TestsScreen openId={null} />;

  if (form) {
    return (
      <div className="screen screen--list">
        <List>
          <Section header="Новый класс" footer="Ученики открывают ссылку класса — и получают твои тесты, а ты видишь их ошибки в тетради.">
            <CreateClass onCreated={onChanged} />
          </Section>
        </List>
      </div>
    );
  }

  return (
    <Placeholder
      className="screen"
      header="Ты пока не в классе"
      description="Учитель присылает ссылку на класс: открой её — и его тесты появятся здесь."
      action={<Button size="l" mode="bezeled" onClick={() => setForm(true)}>Я учитель — создать класс</Button>}
    />
  );
}
