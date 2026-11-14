-- С чем слово путают и как различать: заполняет фоном fill_contrast.
-- null — ещё не разобрано; {"others": []} — путать не с чем.
alter table words add column contrast jsonb;
