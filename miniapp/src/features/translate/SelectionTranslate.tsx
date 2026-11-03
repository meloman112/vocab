import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../../api/client';
import type { Lookup, WordLookup } from '../../api/types';
import { impact, notify } from '../../lib/telegram';
import './translate.css';

/** Сколько ждать, пока выделение «устоится»: пока тянут за ручку, кнопка не прыгает. */
const SETTLE_MS = 300;
/** После этого под «Перевожу…» объясняем, почему долго: новое слово пишет модель. */
const SLOW_MS = 2500;
/** Длиннее — уже абзац: модель переведёт, но читать такое в окошке неудобно. */
const MAX_CHARS = 400;

type Pill = { text: string; x: number; y: number; below: boolean };
type Card =
  | { text: string; state: 'loading'; slow: boolean }
  | { text: string; state: 'ok'; data: Lookup; saving: boolean }
  | { text: string; state: 'error'; message: string };

/** Одно английское слово? Знаки по краям срезаем: «book,» → book. */
function wordFrom(raw: string): string | null {
  const text = raw.replace(/[‘’]/g, "'").replace(/^[^A-Za-z]+|[^A-Za-z]+$/g, '');
  if (!text || text.length > 40) return null;
  return /^[A-Za-z][A-Za-z'-]*$/.test(text) ? text : null;
}

/**
 * Выделенное: слово, фраза или предложение по-английски. У одного слова
 * края чистим, у предложения оставляем знаки — точка и скобки модели нужны.
 * Русское (подсказки, задания) не переводим.
 */
function textFrom(raw: string): string | null {
  const text = raw.replace(/[‘’]/g, "'").replace(/\s+/g, ' ').trim();
  if (!text.includes(' ')) return wordFrom(text);
  if (text.length > MAX_CHARS || /[А-Яа-яЁё]/.test(text)) return null;
  const letters = text.replace(/[^A-Za-z]/g, '').length;
  return letters >= 2 ? text.replace(/^[^A-Za-z(“"']+/, '') : null;
}

/** Текст выделения, если его можно переводить; поля ввода и само окно не в счёт. */
function currentSelection(): { text: string; rect: DOMRect } | null {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null;
  const node = sel.anchorNode;
  const el = node instanceof Element ? node : node?.parentElement;
  if (el?.closest(SKIP)) return null;
  const text = textFrom(sel.toString());
  if (!text) return null;
  const rect = sel.getRangeAt(0).getBoundingClientRect();
  if (!rect.width && !rect.height) return null;
  return { text, rect };
}

const SKIP = 'input, textarea, [contenteditable], .tr-sheet, .tr-pill';
const LETTER = /[A-Za-z'’-]/;

/** Слово под курсором — для правой кнопки без выделения. */
function wordAt(x: number, y: number): string | null {
  const d = document as Document & {
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
  };
  let node: Node | null = null;
  let offset = 0;
  if (d.caretPositionFromPoint) {
    const p = d.caretPositionFromPoint(x, y);
    node = p?.offsetNode ?? null;
    offset = p?.offset ?? 0;
  } else if (d.caretRangeFromPoint) {
    const r = d.caretRangeFromPoint(x, y);
    node = r?.startContainer ?? null;
    offset = r?.startOffset ?? 0;
  }
  if (!node || node.nodeType !== Node.TEXT_NODE || node.parentElement?.closest(SKIP)) return null;
  const text = (node as Text).data;
  let start = offset;
  let end = offset;
  while (start > 0 && LETTER.test(text[start - 1]!)) start--;
  while (end < text.length && LETTER.test(text[end]!)) end++;
  if (start === end) return null;
  // Каретка прилипает к ближайшему тексту: клик в пустоту рядом со словом — не по слову.
  const range = document.createRange();
  range.setStart(node, start);
  range.setEnd(node, end);
  const rect = range.getBoundingClientRect();
  if (x < rect.left - 2 || x > rect.right + 2 || y < rect.top - 2 || y > rect.bottom + 2) return null;
  return wordFrom(text.slice(start, end));
}

/** Правый клик: по выделению — выделенное, иначе слово под курсором. */
function targetAt(x: number, y: number): string | null {
  const s = currentSelection();
  if (s && x >= s.rect.left - 4 && x <= s.rect.right + 4 && y >= s.rect.top - 4 && y <= s.rect.bottom + 4) {
    return s.text;
  }
  return wordAt(x, y);
}

/**
 * Перевод выделенного по всему мини-аппу: выделил слово — под ним кнопка
 * «Перевести», на компьютере то же по правой кнопке мыши. Перевод — из
 * общего словаря бота, оттуда же «Добавить в мои слова».
 */
export function SelectionTranslate() {
  const [pill, setPill] = useState<Pill | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const abort = useRef<AbortController | null>(null);

  const close = useCallback(() => {
    abort.current?.abort();
    abort.current = null;
    setCard(null);
  }, []);

  const open = useCallback((text: string) => {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setPill(null);
    // Своё окно вместо системного меню: выделение больше не нужно, а на
    // телефоне его ручки и «Копировать» висели бы поверх перевода.
    window.getSelection()?.removeAllRanges();
    impact('light');
    setCard({ text, state: 'loading', slow: false });
    const slow = setTimeout(() => {
      setCard((c) => (c?.state === 'loading' && c.text === text ? { ...c, slow: true } : c));
    }, SLOW_MS);
    api.lookup(text, ctrl.signal).then(
      (data) => setCard((c) => (c?.text === text ? { text, state: 'ok', data, saving: false } : c)),
      (e: Error) => {
        if (ctrl.signal.aborted) return;
        setCard((c) => (c?.text === text ? { text, state: 'error', message: e.message } : c));
      },
    ).finally(() => clearTimeout(slow));
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const s = currentSelection();
        if (!s) {
          setPill(null);
          return;
        }
        // Под выделением: сверху на телефоне системное «Копировать | Найти».
        const below = s.rect.bottom + 52 < window.innerHeight;
        const x = Math.min(Math.max(s.rect.left + s.rect.width / 2, 70), window.innerWidth - 70);
        setPill({ text: s.text, x, y: below ? s.rect.bottom + 8 : s.rect.top - 8, below });
      }, SETTLE_MS);
    };
    // Правая кнопка ловится на pointerdown: Telegram Desktop глушит своё
    // контекстное меню, и contextmenu до страницы доходит не всегда.
    // contextmenu остаётся запасным путём и гасит меню браузера.
    let rightAt = 0;
    const onPointer = (e: PointerEvent) => {
      if (e.button !== 2) return;
      const text = targetAt(e.clientX, e.clientY);
      if (!text) return;
      rightAt = Date.now();
      e.preventDefault();
      open(text);
    };
    const onContext = (e: MouseEvent) => {
      if (Date.now() - rightAt < 1000) {
        e.preventDefault();
        return;
      }
      const text = targetAt(e.clientX, e.clientY);
      if (!text) return;
      e.preventDefault();
      open(text);
    };
    // Прокрутили — кнопка осталась бы висеть в стороне от слова.
    const onScroll = () => setPill(null);
    document.addEventListener('selectionchange', onChange);
    document.addEventListener('pointerdown', onPointer, true);
    document.addEventListener('contextmenu', onContext);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      clearTimeout(timer);
      document.removeEventListener('selectionchange', onChange);
      document.removeEventListener('pointerdown', onPointer, true);
      document.removeEventListener('contextmenu', onContext);
      window.removeEventListener('scroll', onScroll);
    };
  }, [open]);

  useEffect(() => {
    if (!card) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [card, close]);

  async function save() {
    if (card?.state !== 'ok' || card.data.kind !== 'word') return;
    const { data } = card;
    setCard({ ...card, saving: true });
    try {
      await api.saveWord(data.id);
      notify('success');
      setCard((c) => (c?.state === 'ok' && c.data.kind === 'word' ? { ...c, saving: false, data: { ...c.data, saved: true } } : c));
    } catch (e) {
      setCard({ text: card.text, state: 'error', message: (e as Error).message });
    }
  }

  return (
    <>
      {pill && !card && (
        <button type="button" className={`tr-pill${pill.below ? '' : ' up'}`}
          style={{ left: pill.x, top: pill.y }}
          // pointerdown, а не click: касание снимает выделение, кнопка исчезла
          // бы раньше, чем сработает. click остаётся для клавиатуры (detail 0).
          onPointerDown={(e) => {
            e.preventDefault();
            open(pill.text);
          }}
          onClick={(e) => {
            if (e.detail === 0) open(pill.text);
          }}>
          Перевести
        </button>
      )}
      {card && (
        <div className="tr-backdrop" onClick={close}>
          <div className="tr-sheet" role="dialog" aria-label={`Перевод: ${card.text}`} onClick={(e) => e.stopPropagation()}>
            <button type="button" className="tr-close" aria-label="Закрыть" onClick={close}>
              ✕
            </button>
            {card.state === 'loading' && (
              <div className="tr-body">
                <div className={card.text.includes(' ') ? 'tr-source' : 'tr-word'}>{card.text}</div>
                <div className="tr-muted tr-wait">
                  Перевожу…
                  {card.slow && !card.text.includes(' ') && (
                    <small>Слова ещё нет в словаре — его пишет ИИ, это до минуты. Дальше будет мгновенно.</small>
                  )}
                </div>
              </div>
            )}
            {card.state === 'error' && (
              <div className="tr-body">
                <div className={card.text.includes(' ') ? 'tr-source' : 'tr-word'}>{card.text}</div>
                <p className="tr-muted">{card.message}</p>
              </div>
            )}
            {card.state === 'ok' &&
              (card.data.kind === 'word' ? (
                <Result data={card.data} saving={card.saving} onSave={save} />
              ) : (
                <div className="tr-body">
                  <div className="tr-source">{card.data.text}</div>
                  <div className="tr-translation">{card.data.translation}</div>
                  <small className="tr-muted">Перевёл ИИ. Слово отсюда — выдели его отдельно, будет с примерами и в карточки.</small>
                </div>
              ))}
          </div>
        </div>
      )}
    </>
  );
}

function Result({ data, saving, onSave }: { data: WordLookup; saving: boolean; onSave: () => void }) {
  const example = data.examples[0];
  return (
    <div className="tr-body">
      <div className="tr-head">
        <span className="tr-word">{data.lemma}</span>
        {data.ipa && <span className="tr-muted">[{data.ipa}]</span>}
        <span className="tr-pos">{data.pos}</span>
      </div>
      {data.form_note && <div className="tr-muted tr-note">{data.form_note}</div>}
      <div className="tr-translation">{data.translation}</div>
      {data.forms && <div className="tr-muted">{data.forms}</div>}
      {example && (
        <div className="tr-example">
          <div>{example.en}</div>
          <div className="tr-muted">{example.ru}</div>
        </div>
      )}
      {data.saved ? (
        <div className="tr-saved">✓ Уже в твоих словах</div>
      ) : (
        <button type="button" className="tr-add" disabled={saving} onClick={onSave}>
          {saving ? 'Добавляю…' : '+ Добавить в мои слова'}
        </button>
      )}
    </div>
  );
}
