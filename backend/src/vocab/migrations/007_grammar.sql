-- Тетрадь по грамматике и учителя. Раньше прогресс тетради жил в Telegram
-- CloudStorage у каждого ученика, и учитель его не видел. Теперь он в базе.

-- Учитель видит ошибки всех учеников тетради. Назначает админ ссылкой из бота.
alter table users add column is_teacher boolean not null default false;

-- Итог ученика по заданию. Ключ задания — «упражнение-индекс» (15-2), как
-- в прежнем мини-аппе: перенесённый из CloudStorage прогресс встаёт на место.
create table grammar_results (
  user_id    bigint  not null references users(id) on delete cascade,
  item       text    not null,
  -- Последний раз решено с первого раза и без подсмотренного ответа.
  clean      boolean not null,
  -- Ошибался хоть раз за всю историю: учителю важно и исправленное.
  was_wrong  boolean not null default false,
  -- Ответы последнего решения по пропускам — для PDF и для учителя.
  answers    jsonb   not null default '[]',
  updated_at timestamptz not null default now(),
  primary key (user_id, item)
);

-- Под рейтинг недели: решённые задания тоже дают XP.
create index grammar_results_time_idx on grammar_results (updated_at);

-- Каждый неверный ответ, как его ввёл ученик, и разбор движка. Это то,
-- ради чего учителю вообще нужен доступ.
create table grammar_mistakes (
  id          bigserial primary key,
  user_id     bigint not null references users(id) on delete cascade,
  item        text   not null,
  slot        int    not null check (slot >= 0),
  answer      text   not null,
  why         text   not null default '',
  created_at  timestamptz not null default now(),
  -- Учитель решил, что ответ верный: ключ его не знал.
  accepted_by bigint references users(id) on delete set null
);

create index grammar_mistakes_user_idx on grammar_mistakes (user_id, created_at desc);
create index grammar_mistakes_item_idx on grammar_mistakes (item, slot);

-- Ответы, засчитанные учителем: дальше они принимаются у всех учеников.
create table grammar_accepted (
  item       text   not null,
  slot       int    not null,
  answer     text   not null,
  added_by   bigint references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (item, slot, answer)
);

-- Одноразовая ссылка t.me/<bot>?start=teach_<code>: кто открыл, тот учитель.
-- Ссылка, а не tg_id: свой id учитель не знает, а бот видит его сам.
create table teacher_invites (
  code       text primary key,
  created_by bigint not null references users(id) on delete cascade,
  created_at timestamptz not null default now(),
  used_by    bigint references users(id) on delete set null,
  used_at    timestamptz
);
