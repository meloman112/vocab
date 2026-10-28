-- Одна лемма — несколько слов: a book «книга» и to book «бронировать».
-- У них разные перевод, примеры и формы, а учить их надо отдельными
-- карточками. Первая запись леммы (меньший id) — основное значение.
alter table words drop constraint words_lemma_key;
alter table words add unique (lemma, pos);
