import type { Gap, Question } from '../../api/types';

interface Props {
  question: Question;
  /** Номер первого пропуска вопроса среди всех пропусков теста. */
  first: number;
  /** Ответы по всем пропускам теста. */
  values?: string[];
  onChange?: (gap: number, value: string) => void;
  marks?: boolean[] | null;
}

export const isGap = (p: string | Gap): p is Gap => typeof p !== 'string';

/** Сколько пропусков в каждом вопросе до него: ответы лежат одним списком. */
export function firstGaps(questions: Question[]): number[] {
  let n = 0;
  return questions.map((q) => {
    const first = n;
    n += q.parts.filter(isGap).length;
    return first;
  });
}

/**
 * Предложение с пропусками. С onChange — поля ввода, с marks — ответы
 * ученика зелёным и красным, с ключом над ошибкой. С values — ответы
 * без отметок, без всего — ключ.
 */
export function QuestionText({ question, first, values, onChange, marks }: Props) {
  let gap = first - 1;
  return (
    <>
      {question.parts.map((p, i) => {
        if (!isGap(p)) return <span key={i}>{p}</span>;
        gap += 1;
        const g = gap;
        const hint = p.hint && <span className="g-verb">({p.hint})</span>;
        if (onChange) {
          return (
            <span key={i} className="g-slot">
              <input value={values?.[g] ?? ''} onChange={(e) => onChange(g, e.target.value)}
                autoCapitalize="off" autoComplete="off" autoCorrect="off" spellCheck={false}
                aria-label={p.hint || `пропуск ${g + 1}`} />
              {hint}
            </span>
          );
        }
        const key = p.answers?.[0] ?? '';
        const given = values?.[g] || '—';
        if (!marks) return <span key={i} className="g-slot"><span className="g-filled">{values ? given : key}</span>{hint}</span>;
        return (
          <span key={i} className={`g-slot${marks[g] ? '' : ' bad'}`}>
            {marks[g] ? <span className="g-filled">{given}</span> : <><s className="g-wrong">{given}</s><span className="g-ans">{key}</span></>}
            {hint}
          </span>
        );
      })}
    </>
  );
}
