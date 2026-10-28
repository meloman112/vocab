-- Уровень CEFR из учебных списков (Oxford 5000, CEFR-J) или от ИИ:
-- по нему новичку сначала выдаются слова A1, а не просто самые частые.
alter table words
  add column level text check (level in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'));
