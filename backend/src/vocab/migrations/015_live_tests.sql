-- Контрольная на уроке: тест с таймером. ends_at — когда время вышло (у обычного
-- домашнего теста null, там срок — дата due); summarized_at — бот уже написал
-- итоги в группу класса, повторно не пишем.
alter table tests add column ends_at timestamptz, add column summarized_at timestamptz;
