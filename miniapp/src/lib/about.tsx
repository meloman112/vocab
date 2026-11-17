import type { MouseEvent } from 'react';

import { openTelegram } from './telegram';

const AUTHORS = [
  { role: 'материалы', name: 'Байрам', username: 'Uralmirzaevich' },
  { role: 'разработка', name: 'Бабур', username: 'Meloman112' },
];

function open(e: MouseEvent<HTMLAnchorElement>) {
  e.preventDefault();
  openTelegram(e.currentTarget.href);
}

/** Подпись авторов: ссылки открываются в Telegram, а не в браузере. */
export function Authors() {
  return (
    <>
      Авторы:{' '}
      {AUTHORS.map((a, i) => (
        <span key={a.username}>
          {i > 0 && ', '}
          <a href={`https://t.me/${a.username}`} onClick={open}>{a.name}</a> — {a.role}
        </span>
      ))}
      . Бесплатно, без подписок и рекламы.
    </>
  );
}
