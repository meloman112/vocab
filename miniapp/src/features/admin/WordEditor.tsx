import { Button, Cell, Input, List, Section, Select, Switch, Textarea } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import { api } from '../../api/client';
import type { AdminWord, Example, Level } from '../../api/types';
import { notify } from '../../lib/telegram';

const LEVELS: Level[] = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
// Пример — строка «english | русский»: так весь список правится одним полем.
const SEPARATOR = ' | ';

function examplesToText(examples: Example[]): string {
  return examples.map((e) => `${e.en}${SEPARATOR}${e.ru}`).join('\n');
}

function textToExamples(text: string): Example[] | null {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const examples = lines.map((line) => {
    const [en = '', ru = ''] = line.split('|').map((p) => p.trim());
    return { en, ru };
  });
  return examples.length > 0 && examples.every((e) => e.en && e.ru) ? examples : null;
}

/** Лемма и часть речи не правятся: это ключ слова, на него ссылаются карточки. */
export function WordEditor({ word, onSaved }: { word: AdminWord; onSaved: () => void }) {
  const [translation, setTranslation] = useState(word.translation);
  const [ipa, setIpa] = useState(word.ipa);
  const [forms, setForms] = useState(word.forms);
  const [irregular, setIrregular] = useState(word.irregular);
  const [level, setLevel] = useState<Level | ''>(word.level ?? '');
  const [examples, setExamples] = useState(examplesToText(word.examples));
  const [banned, setBanned] = useState(word.banned);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const parsed = textToExamples(examples);
  const valid = translation.trim() !== '' && parsed !== null;

  const save = () => {
    if (!parsed) return;
    setSaving(true);
    setError('');
    api.admin
      .save(word.id, { translation, ipa, forms, irregular, examples: parsed, level: level || null, banned })
      .then(
        () => {
          notify('success');
          onSaved();
        },
        (e: Error) => {
          notify('error');
          setError(e.message);
          setSaving(false);
        },
      );
  };

  return (
    <div className="screen screen--list">
      <List>
        <Section header={`${word.lemma} · ${word.pos} — перевод`}>
          <Input value={translation} onChange={(e) => setTranslation(e.target.value)}
                 status={translation.trim() ? 'default' : 'error'} />
        </Section>
        <Section header="Транскрипция IPA">
          <Input value={ipa} onChange={(e) => setIpa(e.target.value)} />
        </Section>
        <Section header="Формы">
          <Input placeholder="go · went · gone" value={forms} onChange={(e) => setForms(e.target.value)} />
        </Section>
        <Section header="Уровень">
          <Select value={level} onChange={(e) => setLevel(e.target.value as Level | '')}>
            <option value="">—</option>
            {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </Select>
        </Section>
        <Section header="Примеры: english | русский, по одному на строку">
          <Textarea value={examples} rows={4} onChange={(e) => setExamples(e.target.value)}
                    status={parsed ? 'default' : 'error'} />
        </Section>
        <Section footer="Сохранение закрывает все жалобы на слово.">
          <Cell Component="label" after={<Switch checked={irregular} onChange={(e) => setIrregular(e.target.checked)} />}>
            Неправильное
          </Cell>
          <Cell Component="label" multiline description="Пропадёт из всех очередей, добавить снова будет нельзя"
                after={<Switch checked={banned} onChange={(e) => setBanned(e.target.checked)} />}>
            В бане
          </Cell>
        </Section>
      </List>
      {error && <Cell multiline className="error">{error}</Cell>}
      {/* Обёртка: прямым ребёнком flex-колонки кнопка растягивается по высоте. */}
      <div className="bottom">
        <Button size="l" stretched disabled={!valid || saving} loading={saving} onClick={save}>
          Сохранить
        </Button>
      </div>
    </div>
  );
}
