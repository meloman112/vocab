-- Класс в Telegram-группе: группа привязана к классу, учитель назначает
-- помощников и задаёт домашку командой в чате.

alter table classes add column chat_id bigint unique;

-- Помощник задаёт домашку и вызывает отчёт, но не видит ответов учителя.
alter table class_members add column assistant boolean not null default false;

-- Одна домашка на класс: новая заменяет старую.
create table homework (
  class_id   bigint primary key references classes(id) on delete cascade,
  exercises  int[]  not null,
  set_by     bigint not null references users(id),
  created_at timestamptz not null default now()
);
