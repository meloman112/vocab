-- Общий словарь: перевод живёт в words один раз на всех, в cards остаётся
-- только личное — расписание FSRS конкретного пользователя.

create table words (
  id          bigserial primary key,
  -- Начальная форма: went и gone приводятся к go до записи.
  lemma       text    unique not null,
  translation text    not null,
  ipa         text    not null,
  pos         text    not null,
  forms       text    not null default '',     -- go · went · gone
  irregular   boolean not null default false,
  examples    jsonb   not null,                -- [{"en": ..., "ru": ...}]
  -- Частота в языке по шкале Zipf (wordfreq): второй ключ сортировки
  -- новых слов после того, сколько людей слово уже учат.
  zipf        real    not null default 0,
  -- Удаления у пользователей нет, а мусор в общем словаре появится.
  -- Флаг, а не delete: удалённое слово тут же добавили бы обратно.
  banned      boolean not null default false,
  created_at  timestamptz not null default now()
);

-- Перенос старых личных карточек. Без перевода ей не место в общем
-- словаре: такое слово владелец просто пришлёт ещё раз.
insert into words (lemma, translation, ipa, pos, examples)
select distinct on (word)
       word, translation, ipa, pos,
       jsonb_build_array(jsonb_build_object('en', example, 'ru', example_ru))
from cards
where status = 'ready'
order by word, created_at;

delete from cards where status <> 'ready';

alter table cards add column word_id bigint references words(id) on delete cascade;
update cards c set word_id = w.id from words w where w.lemma = c.word;
alter table cards alter column word_id set not null;

-- Вместе с колонками уходят unique (user_id, word) и частичный индекс по
-- status — они на них опирались.
alter table cards
  drop column word,
  drop column status,
  drop column translation,
  drop column ipa,
  drop column pos,
  drop column example,
  drop column example_ru,
  drop column source_url;

alter table cards add unique (user_id, word_id);
create index cards_due_idx on cards (user_id, due);
-- Под «сколько человек учат слово» — порядок выдачи новых слов.
create index cards_word_idx on cards (word_id);

-- Счётчик запросов к ИИ на сегодня. Бот публичный, а платим за каждый
-- новый перевод мы.
alter table users
  add column llm_day  date,
  add column llm_used int not null default 0;
