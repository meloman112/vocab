import { Button, Caption, Placeholder, Spinner, Text, Title } from '@telegram-apps/telegram-ui';
import { useEffect, useRef, useState } from 'react';

import { api } from '../../api/client';
import type { DrillVerb, GrammarResult } from '../../api/types';
import type { Book } from './book';
import { checkRow, drillRows, drillTenses, knownTenses, ladder, pickVerb, PEOPLE, weakTense, type DrillRow } from './drill';
import { TENSES, type Tense } from './engine';

/** Сколько неудачных проверок поля, после которых можно посмотреть ответ. */
const FAILS_TO_SHOW = 2;

interface Round {
  /** Номер таблицы: по нему React пересоздаёт поля. */
  id: number;
  verb: string;
  subject: string;
  tenses: Tense[];
  rows: Map<Tense, DrillRow[]>;
}

interface Props {
  book: Book;
  results: Record<string, GrammarResult>;
  onHome: () => void;
}

/** Тренировка форм: один глагол и лицо, каждое время — «+», «−», «?». Результаты нигде не хранятся. */
export function DrillScreen({ book, results, onHome }: Props) {
  const [verbs, setVerbs] = useState<DrillVerb[] | null>(null);
  const [error, setError] = useState('');
  const [round, setRound] = useState<Round | null>(null);
  // Лица идут по кругу, начиная со случайного.
  const turn = useRef(Math.floor(Math.random() * PEOPLE.length));
  const known = ladder(knownTenses(book, results));
  const weak = weakTense(book, results, known);

  useEffect(() => {
    api.grammar.verbs().then(setVerbs, (e: Error) => setError(e.message));
  }, []);

  function start(previousClean: boolean) {
    const verb = pickVerb(verbs!, round?.verb ?? null);
    if (!verb) return setError('Нет глаголов, которые можно проспрягать: добавь слова.');
    const id = turn.current++;
    const { subject, person } = PEOPLE[id % PEOPLE.length]!;
    const tenses = drillTenses(known, verb, weak, previousClean);
    setRound({ id, verb, subject, tenses, rows: new Map(tenses.map((t) => [t, drillRows(verb, subject, person, t)])) });
  }

  useEffect(() => {
    if (verbs && !round) start(false);
  }, [verbs]);

  if (error) return <Placeholder className="screen" header="Тренировка не началась" description={error} />;
  if (!round) return <div className="screen screen--center"><Spinner size="l" /></div>;

  return (
    <Table key={round.id} round={round}
      weak={weak && round.tenses.includes(weak) ? weak : null} onMore={start} onHome={onHome} />
  );
}

interface FieldState {
  text: string;
  fails: number;
  done: boolean;
  /** Верно с первой проверки, без подсказки. */
  firstTry: boolean;
  why?: string;
  more?: string;
}

const emptyField = (): FieldState => ({ text: '', fails: 0, done: false, firstTry: false });

function Table({ round, weak, onMore, onHome }: {
  round: Round;
  weak: Tense | null;
  onMore: (previousClean: boolean) => void;
  onHome: () => void;
}) {
  const { verb, subject, tenses, rows } = round;
  const [fields, setFields] = useState(() => tenses.map(() => [emptyField(), emptyField(), emptyField()]));
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const active = fields.findIndex((block) => !block.every((f) => f.done));
  const finished = active < 0;

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  useEffect(() => {
    inputs.current[0]?.focus();
  }, [active]);

  const patch = (b: number, i: number, change: Partial<FieldState>) =>
    setFields((all) => all.map((block, bi) => (bi !== b ? block : block.map((f, fi) => (fi === i ? { ...f, ...change } : f)))));

  function check() {
    const tense = tenses[active]!;
    setFields((all) => all.map((block, bi) => (bi !== active ? block : block.map((f, i) => {
      if (f.done) return f;
      const row = rows.get(tense)![i]!;
      const d = checkRow(row, f.text);
      if (d.ok) return { ...f, done: true, firstTry: f.fails === 0, why: undefined, more: undefined };
      return { ...f, fails: f.fails + 1, why: d.why, more: d.more };
    }))));
  }

  function onEnter(i: number) {
    const block = fields[active]!;
    const next = block.findIndex((f, j) => j > i && !f.done);
    if (next < 0) return check();
    inputs.current[next]?.focus();
  }

  const total = tenses.length * 3;
  const firstTry = fields.flat().filter((f) => f.firstTry).length;

  return (
    <div className="screen g-drill">
      <header className="g-head">
        <Caption className="g-eyebrow">Тренировка форм</Caption>
        <Title level="1" weight="1" className="g-title">to {verb} · {subject}</Title>
        {weak && <Text className="hint">Чаще всего ошибаешься: {TENSES[weak].name}</Text>}
      </header>

      {tenses.map((tense, b) => {
        if (!finished && b > active) return null;
        const isActive = b === active;
        return (
          <section key={tense} className="g-tense">
            <h3>{TENSES[tense].name}<small>{TENSES[tense].formula}</small></h3>
            {rows.get(tense)!.map((row, i) => (
              <Field key={row.sign} row={row} state={fields[b]![i]!} formula={TENSES[tense].formula}
                inputRef={(el) => { if (isActive) inputs.current[i] = el; }}
                onChange={(text) => patch(b, i, { text, why: undefined, more: undefined })}
                onEnter={() => onEnter(i)}
                onShow={() => patch(b, i, { text: row.answer, done: true, firstTry: false, why: undefined })} />
            ))}
          </section>
        );
      })}

      {finished ? (
        <div className="g-summary">
          <div className="g-result">
            <div className="g-big">{firstTry}/{total}</div>
            <Caption className="hint">форм с первого раза</Caption>
          </div>
          <div className="actions g-actions">
            <Button size="l" mode="bezeled" stretched onClick={() => onMore(firstTry === total)}>Ещё глагол</Button>
            <Button size="l" stretched onClick={onHome}>К упражнениям</Button>
          </div>
        </div>
      ) : (
        <div className="g-bottom">
          <Button size="l" stretched className="g-go" onClick={check}>Проверить</Button>
        </div>
      )}
    </div>
  );
}

function Field({ row, state, formula, inputRef, onChange, onEnter, onShow }: {
  row: DrillRow;
  state: FieldState;
  formula: string;
  inputRef: (el: HTMLInputElement | null) => void;
  onChange: (text: string) => void;
  onEnter: () => void;
  onShow: () => void;
}) {
  const bad = !state.done && state.why !== undefined;
  return (
    <div className={`g-field${state.done ? ' ok' : ''}${bad ? ' bad' : ''}`}>
      <label>
        <span className="g-sign">{row.sign}</span>
        <input ref={inputRef} value={state.text} readOnly={state.done} placeholder={row.sign === '?' ? `… ${row.subject} …?` : `${row.subject} …`}
          autoCapitalize="off" autoCorrect="off" autoComplete="off" spellCheck={false} enterKeyHint="next"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') onEnter(); }} />
      </label>
      {bad && (
        <p className="g-why">
          <b>{state.why}</b> {state.more} <i>Формула: {formula}</i>
          {state.fails >= FAILS_TO_SHOW && <button type="button" onClick={onShow}>Показать ответ</button>}
        </p>
      )}
    </div>
  );
}
