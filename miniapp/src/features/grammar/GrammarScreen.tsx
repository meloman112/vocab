import { Badge, Button, Caption, Cell, List, Placeholder, Section, Spinner, Text, Title } from '@telegram-apps/telegram-ui';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { api } from '../../api/client';
import type { GrammarResult, TopicData } from '../../api/types';
import { shuffle } from '../../lib/shuffle';
import { useBackButton } from '../../lib/telegram';
import { pdfExercises, type Book, type Exercise } from './book';
import { ExerciseRun } from './ExerciseRun';
import { useGrammar } from './useGrammar';
import './grammar.css';

const MIX_SIZE = 10;

type View =
  | { name: 'home' }
  | { name: 'topic'; id: string }
  | { name: 'run'; keys: string[]; title: string; review: boolean; back: View; nonce: number };

/** Тетрадь: темы → упражнения → задания по одному, итоги и работа над ошибками. */
export function GrammarScreen({ onExit }: { onExit: () => void }) {
  const { data, error } = useGrammar();
  const [view, setView] = useState<View>({ name: 'home' });
  const [toastText, setToastText] = useState('');

  const toast = useCallback((text: string) => setToastText(text), []);
  useEffect(() => {
    if (!toastText) return;
    const t = setTimeout(() => setToastText(''), 2500);
    return () => clearTimeout(t);
  }, [toastText]);

  const back = useCallback(() => {
    if (view.name === 'run') setView(view.back);
    else if (view.name === 'topic') setView({ name: 'home' });
    else onExit();
  }, [view, onExit]);
  useBackButton(back);

  // Фигурные скобки обязательны: в новых Chromium scrollTo возвращает
  // Promise, и React принял бы его за функцию очистки — «n is not a function».
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [view]);

  if (error) return <Placeholder className="screen" header="Тетрадь не открылась" description={error} />;
  if (!data) {
    return (
      <div className="screen screen--center">
        <Spinner size="l" />
      </div>
    );
  }

  const { book, progress } = data;
  const results = progress.results;
  const mistakes = () => [...book.items.keys()].filter((k) => results[k] && !results[k].clean);
  const solved = () => [...book.items.keys()].filter((k) => results[k]?.clean);

  const run = (keys: string[], title: string, review: boolean) =>
    setView({ name: 'run', keys, title, review, back: view.name === 'run' ? view.back : view, nonce: Date.now() });
  const startMistakes = () => run(mistakes(), 'Работа над ошибками', true);
  const startMix = () => run(shuffle(solved()).slice(0, MIX_SIZE), 'Вперемешку', true);

  const content = (() => {
    switch (view.name) {
      case 'run':
        return (
          <ExerciseRun key={view.nonce} grammar={data} keys={view.keys} title={view.title} review={view.review}
            onHome={() => setView(view.back)} onMistakes={startMistakes} onMix={startMix} toast={toast} />
        );
      case 'topic': {
        const topic = book.topics.find((t) => t.id === view.id)!;
        return <TopicView book={book} topic={topic} results={results}
          onOpen={(ex) => run(ex.items.map((i) => i.key), `Упражнение ${ex.id}`, false)} />;
      }
      case 'home':
        return <Home book={book} results={results} wrong={mistakes().length} solved={solved().length}
          onTopic={(id) => setView({ name: 'topic', id })} onMistakes={startMistakes} onMix={startMix} toast={toast} />;
    }
  })();

  return (
    <>
      {content}
      {toastText && <div className="g-toast" role="status">{toastText}</div>}
    </>
  );
}

function countDone(book: Book, ids: number[], results: Record<string, GrammarResult>) {
  let total = 0, done = 0, clean = 0, wrong = 0;
  for (const id of ids) {
    for (const item of book.exercises.get(id)!.items) {
      total++;
      const r = results[item.key];
      if (!r) continue;
      done++;
      if (r.clean) clean++;
      else wrong++;
    }
  }
  return { total, done, clean, wrong };
}

function Bar({ ok, warn, total }: { ok: number; warn: number; total: number }) {
  return (
    <div className="g-bar" aria-hidden>
      <i style={{ width: `${(ok / Math.max(total, 1)) * 100}%` }} />
      <i className="warn" style={{ width: `${(warn / Math.max(total, 1)) * 100}%` }} />
    </div>
  );
}

interface HomeProps {
  book: Book;
  results: Record<string, GrammarResult>;
  wrong: number;
  solved: number;
  onTopic: (id: string) => void;
  onMistakes: () => void;
  onMix: () => void;
  toast: (text: string) => void;
}

function Home({ book, results, wrong, solved, onTopic, onMistakes, onMix, toast }: HomeProps) {
  const [sending, setSending] = useState(false);
  const all = useMemo(() => [...book.exercises.keys()], [book]);
  const total = countDone(book, all, results);

  async function sendAll() {
    const done = all.filter((id) => book.exercises.get(id)!.items.some((i) => results[i.key]));
    setSending(true);
    try {
      await api.grammar.pdf(pdfExercises(book, done, results));
      toast('PDF отправлен в чат с ботом');
    } catch (e) {
      toast(`PDF не отправлен: ${(e as Error).message}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="screen screen--list g-home">
      <header className="g-head">
        <Caption className="g-eyebrow">Work book</Caption>
        <Title level="1" weight="1" className="g-title">
          Тетрадь
        </Title>
        <Text className="hint">
          Сделано {total.done} из {total.total} · с первого раза {total.clean}
        </Text>
        <Bar ok={total.clean} warn={total.wrong} total={total.total} />
      </header>

      {(wrong > 0 || solved > 0) && (
        <div className="g-repeat">
          {wrong > 0 && (
            <button type="button" className="g-review" onClick={onMistakes}>
              <div>
                Работа над ошибками
                <small>задания, где была ошибка</small>
              </div>
              <span>{wrong}</span>
            </button>
          )}
          {solved > 0 && (
            <button type="button" className="g-review mix" onClick={onMix}>
              <div>
                Вперемешку
                <small>{MIX_SIZE} случайных из уже сделанных</small>
              </div>
              <span>↻</span>
            </button>
          )}
        </div>
      )}

      <List>
        <Section header="Темы">
          {book.topics.map((topic, i) => {
            const c = countDone(book, topic.exercises.map((e) => e.id), results);
            const range = `${topic.exercises[0]!.id}–${topic.exercises.at(-1)!.id}`;
            return (
              <Cell key={topic.id} onClick={() => onTopic(topic.id)}
                before={<span className="g-topic-num">{i + 1}</span>}
                subtitle={c.done ? `Сделано ${c.done} из ${c.total}` : `Упражнения ${range}`}
                after={c.wrong > 0 ? <Badge type="number" mode="critical">{c.wrong}</Badge>
                  : c.done === c.total ? <span className="g-check">✓</span> : undefined}
                description={c.done > 0 ? <Bar ok={c.clean} warn={c.wrong} total={c.total} /> : undefined}
                multiline>
                {topic.title}
              </Cell>
            );
          })}
        </Section>
      </List>

      {total.done > 0 && (
        <div className="bottom">
          <Button size="l" mode="bezeled" stretched loading={sending} onClick={sendAll}>
            Отправить PDF в чат: всё сделанное
          </Button>
        </div>
      )}
    </div>
  );
}

interface TopicProps {
  book: Book;
  topic: TopicData;
  results: Record<string, GrammarResult>;
  onOpen: (ex: Exercise) => void;
}

function TopicView({ book, topic, results, onOpen }: TopicProps) {
  return (
    <div className="screen g-topic">
      <Title level="2" weight="1" className="g-title">
        {topic.title}
      </Title>
      <details className="g-rules">
        <summary>Правила из Grammar book</summary>
        {topic.rules.map((key) => {
          const rule = book.rules[key];
          if (!rule) return null;
          return (
            <div key={key}>
              <h3>{rule.title}</h3>
              {rule.formula && <div className="g-formula">{rule.formula}</div>}
              <p>{rule.text}</p>
            </div>
          );
        })}
      </details>
      <div className="g-list">
        {topic.exercises.map(({ id }) => {
          const ex = book.exercises.get(id)!;
          const c = countDone(book, [id], results);
          return (
            <button key={id} type="button" className="g-ex-card" onClick={() => onOpen(ex)}>
              <span className="g-ex-num">{id}</span>
              <span className="g-ex-title">{ex.task}</span>
              <span className="g-ex-count">
                {c.done}/{c.total}
              </span>
              <Bar ok={c.clean} warn={c.wrong} total={c.total} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
