import type { QuizCard, QuizSource } from '../../api/types';
import { canSpeak } from '../../lib/speech';

export type ModeId = 'en-ru' | 'ru-en' | 'spell' | 'cloze' | 'irregular' | 'listen' | 'pairs';

export interface Mode {
  id: ModeId;
  icon: string;
  title: string;
  subtitle: string;
  source: QuizSource;
  /** Годится ли карточка: для выбора нужны хотя бы два варианта. */
  fits: (card: QuizCard) => boolean;
}

const hasRu = (card: QuizCard) => card.choices_ru.length >= 2;
const always = () => true;

/** Порядок — от узнавания к воспроизведению: так меню читается как лестница. */
export const MODES: Mode[] = [
  { id: 'en-ru', icon: '🔤', title: 'Выбери перевод', subtitle: 'Слово → один из 4 переводов',
    source: 'any', fits: hasRu },
  { id: 'ru-en', icon: '🔁', title: 'Выбери слово', subtitle: 'Перевод → одно из 4 слов',
    source: 'any', fits: (card) => card.choices_en.length >= 2 },
  { id: 'pairs', icon: '🧩', title: 'Пары', subtitle: 'Соедини 5 слов с переводами',
    source: 'any', fits: always },
  ...(canSpeak
    ? [{ id: 'listen', icon: '🎧', title: 'На слух', subtitle: 'Слушаешь и выбираешь перевод',
         source: 'any', fits: hasRu } satisfies Mode]
    : []),
  { id: 'spell', icon: '⌨️', title: 'Напиши слово', subtitle: 'Перевод → пишешь по-английски',
    source: 'any', fits: always },
  { id: 'cloze', icon: '✍️', title: 'Вставь в пример', subtitle: 'Пропуск в предложении',
    source: 'cloze', fits: (card) => card.cloze !== null },
  { id: 'irregular', icon: '⚡', title: 'Неправильные глаголы', subtitle: 'go → went → gone',
    source: 'irregular', fits: always },
];

export function modeById(id: ModeId): Mode {
  const mode = MODES.find((m) => m.id === id);
  if (!mode) throw new Error(`нет режима ${id}`);
  return mode;
}
