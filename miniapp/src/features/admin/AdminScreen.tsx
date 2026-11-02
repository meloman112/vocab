import { Caption, Placeholder, SegmentedControl, Spinner } from '@telegram-apps/telegram-ui';
import { useCallback, useEffect, useState } from 'react';

import { api } from '../../api/client';
import type { AdminSummary, AdminWord } from '../../api/types';
import { useBackButton } from '../../lib/telegram';
import { DictionaryTab } from './DictionaryTab';
import { ReportsTab } from './ReportsTab';
import { WordEditor } from './WordEditor';

type Tab = 'reports' | 'dictionary';

/** Жалобы и правка общего словаря. Открывается только админам — сервер проверяет сам. */
export function AdminScreen({ onExit }: { onExit: () => void }) {
  const [tab, setTab] = useState<Tab>('reports');
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<AdminWord | null>(null);
  // Сменился — вкладки перечитывают данные после правки слова.
  const [version, setVersion] = useState(0);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  const closeEditor = useCallback(() => setEditing(null), []);

  useBackButton(editing ? closeEditor : onExit);

  useEffect(() => {
    api.admin.summary().then(setSummary, (e: Error) => setError(e.message));
  }, [version]);

  if (error) return <Placeholder header="Админка не открылась" description={error} className="screen" />;
  if (!summary) {
    return (
      <div className="screen screen--center">
        <Spinner size="l" />
      </div>
    );
  }

  if (editing) {
    return (
      <WordEditor
        word={editing}
        onSaved={() => {
          setEditing(null);
          refresh();
        }}
      />
    );
  }

  return (
    <div className="screen screen--list">
      <Caption className="hint admin__summary">
        Людей: {summary.users} · за неделю: {summary.active_week} · слов: {summary.words} · в бане:{' '}
        {summary.banned}
      </Caption>
      <SegmentedControl>
        <SegmentedControl.Item selected={tab === 'reports'} onClick={() => setTab('reports')}>
          Жалобы{summary.open_reports > 0 ? ` · ${summary.open_reports}` : ''}
        </SegmentedControl.Item>
        <SegmentedControl.Item selected={tab === 'dictionary'} onClick={() => setTab('dictionary')}>
          Словарь
        </SegmentedControl.Item>
      </SegmentedControl>
      {tab === 'reports' ? (
        <ReportsTab version={version} onEdit={setEditing} onChanged={refresh} />
      ) : (
        <DictionaryTab version={version} onEdit={setEditing} />
      )}
    </div>
  );
}
