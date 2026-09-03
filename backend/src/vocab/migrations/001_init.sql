-- Начальная схема. Применённую миграцию править нельзя: база, поднятая с нуля,
-- и уже работающая разъедутся молча. Изменение схемы — всегда новый файл.

create table users (
  id         bigserial primary key,
  tg_id      bigint unique not null,
  created_at timestamptz not null default now()
);

create table cards (
  id          bigserial primary key,
  user_id     bigint not null references users(id) on delete cascade,
  word        text   not null,

  -- Обогащение через DeepSeek идёт в фоне, поэтому карточка живёт без перевода.
  status      text   not null default 'pending',   -- pending | ready | failed
  translation text,
  ipa         text,
  pos         text,
  example     text,
  example_ru  text,
  source_url  text,

  -- Состояние FSRS. Имена и типы — как в py-fsrs Card, чтобы обёртка была
  -- перекладыванием полей, а не переводом форматов.
  -- state = 1 (State.Learning): в py-fsrs нумерация начинается с единицы,
  -- нуля в enum нет вовсе.
  state       int    not null default 1,
  step        int             default 0,
  stability   double precision,
  difficulty  double precision,
  due         timestamptz not null default now(),
  last_review timestamptz,

  created_at  timestamptz not null default now(),

  -- Одно и то же слово дважды не добавляется: POST /words возвращает
  -- существующую карточку, а не 409 — букмарклет стреляет не глядя.
  unique (user_id, word)
);

-- Частичный индекс под единственный горячий запрос — выборку очереди.
create index cards_due_idx on cards (user_id, due) where status = 'ready';

-- Нужен не UI, а дообучению параметров FSRS под себя (fsrs.Optimizer).
create table reviews (
  id          bigserial primary key,
  card_id     bigint not null references cards(id) on delete cascade,
  rating      int    not null check (rating between 1 and 4),
  reviewed_at timestamptz not null default now()
);

create index reviews_card_idx on reviews (card_id);
