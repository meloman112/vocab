-- Рекорд игры «Глаголы на скорость» в чате бота: виджет живёт в одном
-- сообщении, а рекорд должен пережить новое.
alter table users add column verbs_best int not null default 0;
