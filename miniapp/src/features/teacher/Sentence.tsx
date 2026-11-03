import { filled, type Book } from '../grammar/book';

interface Props {
  book: Book;
  itemKey: string;
  /** Ответы ученика; без них — ключ. */
  answers?: (string | null)[];
}

/** Задание с ответами: зелёным — то, что стоит в пропусках. */
export function Sentence({ book, itemKey, answers }: Props) {
  const item = book.items.get(itemKey);
  if (!item) return <span className="hint">Задание {itemKey} убрано из тетради</span>;
  return (
    <div className="g-mistake">
      <span className="g-num">
        {item.ex}.{item.n}
      </span>
      {filled(book, itemKey, answers).map((p, i) => (p.answer ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}
    </div>
  );
}
