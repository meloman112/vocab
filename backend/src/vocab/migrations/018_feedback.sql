-- Отзывы, идеи и ошибки от пользователей. Админ получает их в Telegram с
-- черновиком ответа от ИИ и решает: отправить, переписать или не отвечать.
create table feedback (
  id          bigserial primary key,
  user_id     bigint not null references users(id) on delete cascade,
  kind        text   not null check (kind in ('review', 'idea', 'bug', 'exercise')),
  text        text   not null,
  -- Задание тетради «12-3», если ошибка в упражнении.
  item        text,
  draft       text,
  answer      text,
  status      text   not null default 'new' check (status in ('new', 'answered', 'skipped')),
  created_at  timestamptz not null default now(),
  closed_at   timestamptz
);
