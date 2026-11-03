import { Button } from '@telegram-apps/telegram-ui';
import { Fragment, useEffect, useReducer, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react';

import type { GrammarMistakeIn } from '../../api/types';
import { impact, notify, useNoVerticalSwipes } from '../../lib/telegram';
import { capitalizeAt, partsOf, ruleFor, slotsOf } from './book';
import { bracketLabel, diagnose, norm, type Diagnosis, type Slot } from './engine';
import { RunSummary } from './RunSummary';
import type { Grammar } from './useGrammar';

type Mode = 'type' | 'tiles';
const MODE_KEY = 'grammar.mode';

function loadMode(): Mode {
  try {
    return localStorage.getItem(MODE_KEY) === 'tiles' ? 'tiles' : 'type';
  } catch {
    return 'type';
  }
}

function shuffle<T>(a: T[]): T[] {
  const b = [...a];
  for (let i = b.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [b[i], b[j]] = [b[j]!, b[i]!];
  }
  return b;
}

type Bad = Diagnosis & { j: number };

/** Состояние одного задания в этом заходе: что введено, что разобрано. */
interface Session {
  vals: string[];
  placed: number[][];
  order: number[][];
  done: boolean[];
  shown: boolean[];
  errors: number;
  active: number;
  bad: Bad[];
  /** Задание впервые решается в этом заходе (а не открыто уже сделанным). */
  fresh: boolean;
  hints: number;
  /** Неверные ответы по порядку — их увидит учитель. */
  log: GrammarMistakeIn[];
}

export interface RunProps {
  grammar: Grammar;
  keys: string[];
  title: string;
  /** Работа над ошибками или «вперемешку»: решённое решается заново. */
  review: boolean;
  onHome: () => void;
  onMistakes: () => void;
  onMix: () => void;
  toast: (text: string) => void;
}

export function ExerciseRun(props: RunProps) {
  const { grammar, keys, title, review, toast } = props;
  const { book, progress, save } = grammar;
  const [pos, setPos] = useState(() => (review ? 0 : Math.max(0, keys.findIndex((k) => !progress.results[k]))));
  const [summary, setSummary] = useState(false);
  const [mode, setMode] = useState<Mode>(loadMode);
  const sessions = useRef(new Map<string, Session>());
  const [, rerender] = useReducer((x: number) => x + 1, 0);
  const sheetRef = useRef<HTMLDivElement>(null);

  useNoVerticalSwipes(mode === 'tiles' && !summary);

  const key = keys[pos]!;
  const item = book.items.get(key)!;
  const ex = book.exercises.get(item.ex)!;
  const parts = partsOf(book, key);
  const slots = slotsOf(book, key);
  const accepted = progress.accepted[key] ?? {};

  function session(k: string): Session {
    let s = sessions.current.get(k);
    if (!s) {
      const ss = slotsOf(book, k);
      const r = !review && progress.results[k];
      s = {
        vals: ss.map((_, j) => (r ? r.answers[j] ?? '' : '')),
        placed: ss.map(() => []),
        order: ss.map((slot) => shuffle(slot.tiles.map((_, i) => i))),
        done: ss.map(() => !!r),
        shown: ss.map(() => false),
        errors: 0,
        active: 0,
        bad: [],
        fresh: !r,
        hints: 0,
        log: [],
      };
      sessions.current.set(k, s);
    }
    return s;
  }

  const s = session(key);
  const finished = s.done.every(Boolean);
  if (!finished && s.done[s.active]) s.active = s.done.findIndex((d) => !d);

  // Новое задание — фокус в первый пропуск, но без прокрутки страницы.
  useEffect(() => {
    if (mode !== 'type' || finished) return;
    sheetRef.current?.querySelector<HTMLElement>('input, textarea')?.focus({ preventScroll: true });
  }, [key, mode, finished]);

  function changeMode(m: Mode) {
    setMode(m);
    try {
      localStorage.setItem(MODE_KEY, m);
    } catch {
      // Режим просто не запомнится — не страшно.
    }
  }

  function check() {
    s.bad = [];
    slots.forEach((slot, j) => {
      if (s.done[j]) return;
      const value = mode === 'type' ? s.vals[j]! : s.placed[j]!.map((i) => slot.tiles[i]).join(' ');
      const d = diagnose(value, slot, accepted[j] ?? []);
      if (d.ok) {
        s.done[j] = true;
        s.vals[j] = value.trim();
        return;
      }
      s.bad.push({ j, ...d });
      if (d.why !== 'Пусто.') s.log.push({ slot: j, answer: value.trim().slice(0, 300), why: `${d.why} ${d.more ?? ''}`.trim() });
    });
    if (s.bad.some((b) => b.why !== 'Пусто.')) {
      s.errors++;
      notify('error');
    }
    if (s.done.every(Boolean)) finish();
    rerender();
  }

  function finish() {
    const clean = s.errors === 0 && !s.shown.some(Boolean);
    notify(clean ? 'success' : 'warning');
    save({ item: key, clean, answers: s.vals.map((v) => v.trim()), mistakes: s.log }).catch((e: Error) => {
      console.error('итог задания не сохранён:', e);
      toast('Не сохранилось — проверь интернет');
    });
    s.log = [];
  }

  function next() {
    if (pos < keys.length - 1) setPos(pos + 1);
    else setSummary(true);
  }

  function place(j: number, i: number) {
    impact('light');
    s.placed[j]!.push(i);
    const full = (k: number) => s.placed[k]!.length >= norm(slots[k]!.ans[0]!).split(' ').length;
    if (full(j)) {
      const nextSlot = slots.findIndex((_, k) => !s.done[k] && !full(k));
      if (nextSlot >= 0) s.active = nextSlot;
    }
    rerender();
  }

  if (summary) return <RunSummary {...props} />;

  const last = pos === keys.length - 1;
  let before = '';
  let j = 0;

  return (
    <div className="screen g-run">
      <header className="g-top">
        <div className="g-top__t">
          <b>{title}</b>
          <span>
            {pos + 1} из {keys.length}
          </span>
        </div>
        <div className="g-modes" role="group" aria-label="Как отвечать">
          {(['type', 'tiles'] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => changeMode(m)}>
              {m === 'type' ? 'Пишу' : 'Плитки'}
            </button>
          ))}
        </div>
      </header>

      <nav className="g-dots" aria-label="Задания">
        {keys.map((k, i) => {
          const r = progress.results[k];
          const cls = r ? (r.clean ? ' ok' : ' fixed') : '';
          return (
            <button key={k} type="button" className={`g-dot${cls}${i === pos ? ' cur' : ''}`} onClick={() => setPos(i)}
              aria-label={`Задание ${book.items.get(k)!.n}`}>
              {book.items.get(k)!.n}
            </button>
          );
        })}
      </nav>

      {/* key — задание: поля ввода неуправляемые и должны пересоздаваться. */}
      <section className="g-sheet" ref={sheetRef} key={`${key}-${mode}`}>
        <p className="g-task">{review ? `Упражнение ${ex.id}. ${ex.task}` : ex.task}</p>
        <div className="g-sent">
          <span className="g-num">{item.n}.</span>
          {parts.map((p, pi) => {
            if (typeof p === 'string') {
              before += p;
              return <Fragment key={pi}>{p}</Fragment>;
            }
            const idx = j++;
            const at = before;
            before += s.vals[idx] || p.ans[0];
            return (
              <SlotView key={pi} slot={p} idx={idx} before={at} s={s} mode={mode}
                onChange={(v) => { s.vals[idx] = v; }}
                onEnter={() => {
                  const empty = [...(sheetRef.current?.querySelectorAll<HTMLInputElement>('.g-slot input, .g-slot textarea') ?? [])]
                    .find((el) => el.dataset.slot !== String(idx) && !el.value.trim());
                  if (empty) empty.focus();
                  else check();
                }}
                onActivate={() => { s.active = idx; rerender(); }}
                onUnplace={(i) => { s.placed[idx] = s.placed[idx]!.filter((x) => x !== i); s.active = idx; rerender(); }}
              />
            );
          })}
        </div>

        {mode === 'tiles' && !finished && (
          <Bank slot={slots[s.active]!} j={s.active} s={s} many={slots.length > 1} onPlace={place} />
        )}

        <FeedbackView s={s} slots={slots} fresh={s.fresh} clean={progress.results[key]?.clean}
          rule={ruleFor(book, ex, s.bad.find((b) => b.rule)?.rule, slots.find((x) => x.tense)?.tense)}
          onHint={(n) => { s.hints = n; rerender(); }}
          onShow={() => { for (const b of s.bad) s.shown[b.j] = true; s.hints = 3; rerender(); }} />
      </section>

      <div className="g-bottom">
        {finished ? (
          <Button size="l" stretched mode="filled" className="g-go" onClick={next}>
            {last ? 'Итоги' : 'Дальше →'}
          </Button>
        ) : (
          <Button size="l" stretched onClick={check}>
            Проверить
          </Button>
        )}
      </div>
    </div>
  );
}

interface SlotProps {
  slot: Slot;
  idx: number;
  before: string;
  s: Session;
  mode: Mode;
  onChange: (value: string) => void;
  onEnter: () => void;
  onActivate: () => void;
  onUnplace: (tile: number) => void;
}

/** Длинный ответ (целое предложение) — поле во всю ширину на новой строке. */
const isWide = (slot: Slot) => slot.ans[0]!.length > 24;

function SlotView({ slot, idx, before, s, mode, onChange, onEnter, onActivate, onUnplace }: SlotProps) {
  const label = bracketLabel(slot);
  const wide = isWide(slot);
  if (s.done[idx]) {
    return <span className={`g-slot${wide ? ' wide' : ''}`}><span className="g-filled">{capitalizeAt(before, s.vals[idx] || slot.ans[0]!)}</span></span>;
  }
  const bad = s.bad.some((b) => b.j === idx);
  const shown = s.shown[idx] && <span className="g-ans">{capitalizeAt(before, slot.ans[0]!)}</span>;

  if (mode === 'type') {
    const common = {
      'data-slot': idx,
      defaultValue: s.vals[idx],
      autoComplete: 'off',
      autoCapitalize: 'off',
      spellCheck: false,
      enterKeyHint: 'go' as const,
      'aria-label': label || 'Пропуск',
      onChange: (e: { target: { value: string } }) => onChange(e.target.value),
      onKeyDown: (e: KeyboardEvent) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        onEnter();
      },
    };
    return (
      <span className={`g-slot${bad ? ' bad' : ''}${wide ? ' wide' : ''}`}>
        {shown}
        {wide ? <textarea rows={2} {...common} /> : <input {...common} />}
        {label && <span className="g-verb">{label}</span>}
      </span>
    );
  }

  return (
    <span className={`g-slot${bad ? ' bad' : ''}${wide ? ' wide' : ''}`}>
      {shown}
      <span className={`g-drop${s.active === idx ? ' active' : ''}`} data-slot={idx} onClick={(e) => { if (e.target === e.currentTarget) onActivate(); }}>
        {s.placed[idx]!.map((i) => (
          <button key={i} type="button" className="g-tile" onClick={() => onUnplace(i)}>
            {slot.tiles[i]}
          </button>
        ))}
      </span>
      {label && <span className="g-verb">{label}</span>}
    </span>
  );
}

interface BankProps {
  slot: Slot;
  j: number;
  s: Session;
  many: boolean;
  onPlace: (j: number, tile: number) => void;
}

function Bank({ slot, j, s, many, onPlace }: BankProps) {
  return (
    <div>
      {many && <div className="g-bank-label">Плитки для {bracketLabel(slot) || `пропуска ${j + 1}`}</div>}
      <div className="g-bank">
        {s.order[j]!.filter((i) => !s.placed[j]!.includes(i)).map((i) => (
          <Tile key={i} text={slot.tiles[i]!} j={j} onPlace={() => onPlace(j, i)} />
        ))}
      </div>
    </div>
  );
}

/** Плитка: нажатие кладёт её в пропуск, а можно и перетащить пальцем. */
function Tile({ text, j, onPlace }: { text: string; j: number; onPlace: () => void }) {
  const dragged = useRef(false);

  function onPointerDown(e: ReactPointerEvent<HTMLButtonElement>) {
    const start = { x: e.clientX, y: e.clientY };
    let ghost: HTMLSpanElement | null = null;
    let over: Element | null = null;
    dragged.current = false;
    const move = (ev: PointerEvent) => {
      if (!ghost && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 8) return;
      if (!ghost) {
        ghost = document.createElement('span');
        ghost.className = 'g-tile ghost';
        ghost.textContent = text;
        document.body.append(ghost);
        dragged.current = true;
      }
      ghost.style.left = `${ev.clientX - 24}px`;
      ghost.style.top = `${ev.clientY - 20}px`;
      const hit = document.elementFromPoint(ev.clientX, ev.clientY)?.closest('.g-drop') ?? null;
      over?.classList.remove('hover');
      over = hit && (hit as HTMLElement).dataset.slot === String(j) ? hit : null;
      over?.classList.add('hover');
    };
    const up = () => {
      removeEventListener('pointermove', move);
      removeEventListener('pointerup', up);
      if (!ghost) return;
      ghost.remove();
      over?.classList.remove('hover');
      if (over) onPlace();
      setTimeout(() => { dragged.current = false; }, 0);
    };
    addEventListener('pointermove', move);
    addEventListener('pointerup', up);
  }

  return (
    <button type="button" className="g-tile" onPointerDown={onPointerDown} onClick={() => { if (!dragged.current) onPlace(); }}>
      {text}
    </button>
  );
}

interface FeedbackProps {
  s: Session;
  slots: Slot[];
  fresh: boolean;
  clean: boolean | undefined;
  rule: ReturnType<typeof ruleFor>;
  onHint: (n: number) => void;
  onShow: () => void;
}

/** Подсказки лесенкой: правило из Grammar book → формула → ответ красной ручкой. */
function FeedbackView({ s, slots, fresh, clean, rule, onHint, onShow }: FeedbackProps) {
  if (s.done.every(Boolean)) {
    if (!fresh) return <div className="g-fb ok">{clean ? 'Сделано с первого раза ✓' : 'Сделано, была ошибка'}</div>;
    const slipped = s.errors || s.shown.some(Boolean);
    return <div className="g-fb ok">{slipped ? 'Верно ✓ Задание вернётся в работе над ошибками.' : 'Верно ✓'}</div>;
  }
  if (!s.bad.length) return null;
  const onlyEmpty = s.bad.every((b) => b.why === 'Пусто.');
  const steps = ['Правило', 'Формула', 'Показать ответ'];

  return (
    <div className="g-fb bad" role="status">
      {s.bad.map((b) => (
        <div key={b.j} className="g-why">
          {slots.length > 1 && <small>{bracketLabel(slots[b.j]!) || `Пропуск ${b.j + 1}`}</small>}
          {b.why} <span>{b.more}</span>
        </div>
      ))}
      {!onlyEmpty && rule && (
        <>
          {s.hints >= 1 && (
            <div className="g-book">
              <small>Grammar book · {rule.title}</small>
              {rule.text}
            </div>
          )}
          {s.hints >= 2 && rule.formula && (
            <div className="g-book">
              <small>{rule.title}</small>
              <div className="g-formula">{rule.formula}</div>
            </div>
          )}
          <div className="g-ladder">
            {steps.map((label, i) => (
              <button key={label} type="button" disabled={i !== s.hints} onClick={() => (i === 2 ? onShow() : onHint(i + 1))}>
                {label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
