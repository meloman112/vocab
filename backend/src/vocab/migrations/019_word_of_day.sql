-- Слово дня из тетради: раз в день бот присылает слово из решённого
-- упражнения. Кнопка «Не присылать» выключает рассылку навсегда.
alter table users add column word_of_day boolean not null default true;
