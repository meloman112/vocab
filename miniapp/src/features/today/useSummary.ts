import { useCallback, useState } from 'react';

import { api } from '../../api/client';
import type { Leaderboard, Me, Stats, StudentTest } from '../../api/types';

/** Цифры для вкладок. null — ещё не пришло: каждая часть грузится сама по себе. */
export interface Summary {
  stats: Stats | null;
  me: Me | null;
  tests: StudentTest[] | null;
  board: Leaderboard | null;
  /** Открытые жалобы; null — не админ. */
  reports: number | null;
  error: string;
}

const EMPTY: Summary = { stats: null, me: null, tests: null, board: null, reports: null, error: '' };

export function useSummary(): { summary: Summary; reload: () => void } {
  const [summary, setSummary] = useState(EMPTY);

  const reload = useCallback(() => {
    const put = (part: Partial<Summary>) => setSummary((s) => ({ ...s, ...part }));
    const fail = (e: Error) => put({ error: e.message });
    put({ error: '' });
    api.stats().then((stats) => put({ stats }), fail);
    api.tests.list().then((tests) => put({ tests }), fail);
    api.leaderboard().then((board) => put({ board }), fail);
    api.me()
      .then(async (me) => put({ me, reports: me.is_admin ? (await api.admin.summary()).open_reports : null }))
      .catch(fail);
  }, []);

  return { summary, reload };
}
