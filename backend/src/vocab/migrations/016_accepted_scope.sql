-- Бот открыт всем: учителем становится любой, кто создал класс. Ответ, который
-- засчитал такой учитель, действует только у него и у учеников его классов —
-- иначе ключ тетради правил бы кто угодно для всех.

-- Чьим ученикам засчитан ответ. Пусто — всем: его засчитал админ или ИИ,
-- и такими остаются все прежние строки.
alter table grammar_accepted add column teacher_id bigint references users(id) on delete cascade;

-- Один и тот же ответ теперь могут засчитать разные учителя.
alter table grammar_accepted drop constraint grammar_accepted_pkey;
create unique index grammar_accepted_key on grammar_accepted (item, slot, answer, coalesce(teacher_id, 0));
