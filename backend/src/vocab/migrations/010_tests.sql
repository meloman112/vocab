-- Тесты учителя. Учитель собирает класс по ссылке t.me/<bot>?start=class_<code>
-- и шлёт ему тест: предложения с пропусками, ответ ученик вписывает руками.

create table classes (
  id         bigserial primary key,
  teacher_id bigint not null references users(id) on delete cascade,
  name       text   not null,
  -- Ссылка многоразовая: по ней заходит весь класс.
  code       text   not null unique,
  created_at timestamptz not null default now()
);

create table class_members (
  class_id  bigint not null references classes(id) on delete cascade,
  user_id   bigint not null references users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  primary key (class_id, user_id)
);

create index class_members_user_idx on class_members (user_id);

create table tests (
  id         bigserial primary key,
  class_id   bigint not null references classes(id) on delete cascade,
  title      text   not null,
  -- [{"parts": ["She ", {"answers": ["doesn't like"], "hint": "not like"}, " coffee."]}]
  -- Ответы учителя лежат здесь же: ученик их не получает до срока.
  questions  jsonb  not null,
  -- Последний день сдачи включительно, по часовому поясу приложения.
  due        date   not null,
  created_at timestamptz not null default now()
);

create index tests_class_idx on tests (class_id);

-- Одна попытка: строка появляется при сдаче и больше не меняется.
-- Балл не хранится: «Засчитать» у учителя меняет его задним числом.
create table test_submissions (
  test_id      bigint not null references tests(id) on delete cascade,
  user_id      bigint not null references users(id) on delete cascade,
  -- Ответы по пропускам подряд, через все вопросы.
  answers      jsonb  not null,
  submitted_at timestamptz not null default now(),
  primary key (test_id, user_id)
);

-- Ответ, который учитель засчитал: верен для этого пропуска у всех.
create table test_accepted (
  test_id bigint not null references tests(id) on delete cascade,
  gap     int    not null check (gap >= 0),
  -- Нормализованный (см. classwork.norm), как и сравнение.
  answer  text   not null,
  primary key (test_id, gap, answer)
);
