import { Button, Caption, Cell, Input, List, Placeholder, Section, Select, Spinner, Textarea } from '@telegram-apps/telegram-ui';
import { useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { ConvertedLine, SchoolClass, TestPreview } from '../../api/types';
import { notify } from '../../lib/telegram';
import { firstGaps, QuestionText } from './QuestionText';

const EXAMPLE = "She [doesn't like] (not like) coffee.\nI [have lived|have been living] (live) here for five years.";

function inDays(n: number): string {
  const d = new Date(Date.now() + n * 86_400_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Учитель пишет вопросы строками или отдаёт готовую контрольную ИИ. */
export function TestEditor({ onSent }: { onSent: () => void }) {
  const [classes, setClasses] = useState<SchoolClass[] | null>(null);
  const [title, setTitle] = useState('');
  const [classId, setClassId] = useState(0);
  const [due, setDue] = useState(inDays(3));
  const [text, setText] = useState('');
  const [preview, setPreview] = useState<TestPreview | null>(null);
  const [notes, setNotes] = useState<ConvertedLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState<number | null>(null);

  useEffect(() => {
    api.teacher.classes().then((list) => {
      setClasses(list);
      setClassId(list[0]?.id ?? 0);
    }, (e: Error) => setError(e.message));
  }, []);

  // Разбирает текст сервер — тот же разбор, что и при сохранении.
  useEffect(() => {
    if (!text.trim()) return setPreview(null);
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api.teacher.preview(text, ctrl.signal).then((p) => {
        setPreview(p);
        setError('');
      }, (e: Error) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    }, 400);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [text]);

  async function send() {
    setBusy(true);
    setError('');
    try {
      const result = await api.teacher.createTest({ title: title.trim(), class_id: classId, due, text });
      notify('success');
      setSent(result.sent);
    } catch (e) {
      notify('error');
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!classes) {
    return error
      ? <Placeholder className="screen" header="Не открылось" description={error} />
      : <div className="screen screen--center"><Spinner size="l" /></div>;
  }
  if (!classes.length) {
    return <Placeholder className="screen" header="Сначала класс" description="Создай класс и раздай ученикам ссылку — тест уходит классу." />;
  }
  if (sent !== null) {
    return (
      <Placeholder className="screen" header={`Отправлено: ${sent}`}
        description="Бот написал каждому ученику класса. За день до срока не сдавшим придёт напоминание."
        action={<Button size="l" onClick={onSent}>К тестам</Button>} />
    );
  }

  const ready = title.trim() && preview && preview.questions.length > 0 && preview.errors.length === 0;
  const firsts = firstGaps(preview?.questions ?? []);
  return (
    <div className="screen screen--list">
      <List>
        <Section header="Название">
          <Input value={title} placeholder="Контрольная: времена" onChange={(e) => setTitle(e.target.value)} />
        </Section>
        <Section header="Кому и до какого числа">
          <Select value={classId} onChange={(e) => setClassId(Number(e.target.value))}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.members})</option>)}
          </Select>
          <Input type="date" value={due} min={inDays(0)} onChange={(e) => setDue(e.target.value)} />
        </Section>

        <Section header="Вопросы, по одному на строку">
          <Textarea rows={8} value={text} placeholder={EXAMPLE} onChange={(e) => setText(e.target.value)} />
          <div className="t-format">
            <span>Ответ — в квадратных скобках: <code>[doesn't like]</code>. Если верных ответов несколько — через <code>|</code>. Подсказка ученику — в круглых скобках сразу после пропуска.</span>
            <b>Сокращения засчитываются сами, второй вариант писать не нужно:</b>
            <div className="t-eq">
              <span>don't, doesn't, didn't</span><span>do / does / did not</span>
              <span>I'm, you're, we've</span><span>I am, you are, we have</span>
              <span>won't, can't, I'll</span><span>will not, cannot, I will</span>
            </div>
            <span className="t-note"><i>'s</i> (is / has) и <i>'d</i> (would / had) не раскрываются: если верны оба, впиши второй через <code>|</code>.</span>
          </div>
        </Section>

        <AiImport onLines={(lines) => {
          setNotes(lines.filter((l) => l.guessed || l.error));
          setText((t) => [t.trim(), ...lines.map((l) => l.line)].filter(Boolean).join('\n'));
        }} />

        {notes.length > 0 && (
          <Section header="Проверь после ИИ">
            {notes.map((n, i) => (
              <Cell key={i} multiline subtitle={n.error ? `не разобралось: ${n.error}` : n.note}>{n.line}</Cell>
            ))}
          </Section>
        )}

        {preview && (
          <Section header={`Так увидит ученик · вопросов: ${preview.questions.length}`}>
            {preview.errors.map((e) => (
              <Cell key={e.line} multiline className="t-err">{e.line ? `Строка ${e.line}: ` : ''}{e.error}</Cell>
            ))}
            <div className="g-sheet t-preview">
              {preview.questions.map((q, i) => (
                <div key={i} className="g-sent"><span className="g-num">{i + 1}.</span><QuestionText question={q} first={firsts[i]!} /></div>
              ))}
            </div>
          </Section>
        )}
      </List>
      {error && <Cell multiline className="error">{error}</Cell>}
      <div className="bottom">
        <Button size="l" stretched disabled={!ready || busy} loading={busy} onClick={send}>
          Отправить классу
        </Button>
      </div>
    </div>
  );
}

function AiImport({ onLines }: { onLines: (lines: ConvertedLine[]) => void }) {
  const [source, setSource] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run(body: { text?: string; docx?: string }) {
    setBusy(true);
    setError('');
    try {
      const lines = await api.teacher.convert(body);
      if (!lines.length) throw new Error('ИИ не нашёл в тексте заданий с пропусками');
      onLines(lines);
      setSource('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function pick(file: File | undefined) {
    if (!file) return;
    if (file.name.toLowerCase().endsWith('.docx')) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = '';
      for (const b of bytes) binary += String.fromCharCode(b);
      return run({ docx: btoa(binary) });
    }
    return run({ text: await file.text() });
  }

  return (
    <Section header="Готовая контрольная"
      footer="Вставь текст или выбери файл Word / .txt. ИИ найдёт пропуски и ответы и добавит строки в поле выше. Большая контрольная разбирается несколько минут — не закрывай приложение.">
      <Textarea rows={4} value={source} placeholder="1. She (not like) coffee. — doesn't like" onChange={(e) => setSource(e.target.value)} />
      <div className="t-format">
        <label className="t-file">
          Выбрать файл Word или .txt
          <input type="file" accept=".docx,.txt" hidden disabled={busy}
            onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ''; }} />
        </label>
        <Button size="m" mode="bezeled" disabled={!source.trim() || busy} loading={busy} onClick={() => run({ text: source })}>
          Разобрать текст с ИИ
        </Button>
        {busy && <Caption className="hint">ИИ читает контрольную…</Caption>}
        {error && <span className="t-err">{error}</span>}
      </div>
    </Section>
  );
}
