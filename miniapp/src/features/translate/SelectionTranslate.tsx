import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../../api/client';
import type { Lookup } from '../../api/types';
import { impact, notify } from '../../lib/telegram';
import './translate.css';

/** Сколько ждать, пока выделение «устоится»: пока тянут за ручку, кнопка не прыгает. */
const SETTLE_MS = 300;
/** После этого под «Перевожу…» объясняем, почему долго: новое слово пишет модель. */
const SLOW_MS = 2500;
const MAX_WORDS = 4;

type Pill = { text: string; x: number; y: number; below: boolean };
type Card =
  | { text: string; state: 'loading'; slow: boolean }
  | { text: string; state: 'ok'; data: Lookup; saving: boolean }
  | { text: string; state: 'error'; message: string };

/** Выделенное — английское слово или короткая фраза? Знаки по краям срезаем: «book,» → book. */
function wordFrom(raw: string): string | null {
  const text = raw.replace(/[‘’]/g, "'").replace(/^[^A-Za-z]+|[^A-Za-z]+$/g, '').replace(/\s+/g, ' ');
  if (!text || text.length > 40) return null;
  if (!/^[A-Za-z][A-Za-z' -]*$/.test(text)) return null;
  if (text.split(' ').length > MAX_WORDS) return null;
  return text;
}

/** Текст выделения, если его можно переводить; поля ввода и само окно не в счёт. */
function currentSelection(): { text: string; rect: DOMRect } | null {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null;
  const node = sel.anchorNode;
  const el = node instanceof Element ? node : node?.parentElement;
  if (el?.closest('input, textarea, [contenteditable], .tr-sheet, .tr-pill')) return null;
  const text = wordFrom(sel.toString());
  if (!text) return null;
  const rect = sel.getRangeAt(0).getBoundingClientRect();
  if (!rect.width && !rect.height) return null;
  return { text, rect };
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
    const onContext = (e: MouseEvent) => {
      const s = currentSelection();
      if (!s) return;
      e.preventDefault();
      open(s.text);
    };
    // Прокрутили — кнопка осталась бы висеть в стороне от слова.
    const onScroll = () => setPill(null);
    document.addEventListener('selectionchange', onChange);
    document.addEventListener('contextmenu', onContext);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      clearTimeout(timer);
      document.removeEventListener('selectionchange', onChange);
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
    if (card?.state !== 'ok') return;
    const { data } = card;
    setCard({ ...card, saving: true });
    try {
      await api.saveWord(data.id);
      notify('success');
      setCard((c) => (c?.state === 'ok' ? { ...c, saving: false, data: { ...c.data, saved: true } } : c));
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
                <div className="tr-word">{card.text}</div>
                <div className="tr-muted tr-wait">
                  Перевожу…
                  {card.slow && <small>Слова ещё нет в словаре — его пишет ИИ, это до минуты. Дальше будет мгновенно.</small>}
                </div>
              </div>
            )}
            {card.state === 'error' && (
              <div className="tr-body">
                <div className="tr-word">{card.text}</div>
                <p className="tr-muted">{card.message}</p>
              </div>
            )}
            {card.state === 'ok' && <Result data={card.data} saving={card.saving} onSave={save} />}
          </div>
        </div>
      )}
    </>
  );
}

function Result({ data, saving, onSave }: { data: Lookup; saving: boolean; onSave: () => void }) {
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
