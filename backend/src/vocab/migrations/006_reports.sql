-- Жалобы на слово общего словаря: опечатка вместо слова (helf), неверный
-- перевод, плохой пример. Разбирает админ в мини-аппе.
create table reports (
  id          bigserial primary key,
  word_id     bigint not null references words(id) on delete cascade,
  user_id     bigint not null references users(id) on delete cascade,
  reason      text   not null check (reason in ('typo', 'translation', 'example', 'other')),
  comment     text,
  created_at  timestamptz not null default now(),
  -- Разобранная жалоба остаётся в истории: видно, что слово уже чинили.
  resolved_at timestamptz
);

-- Одна открытая жалоба от человека на слово: повторное нажатие меняет
-- причину, а не плодит строки.
create unique index reports_open_idx on reports (word_id, user_id) where resolved_at is null;
