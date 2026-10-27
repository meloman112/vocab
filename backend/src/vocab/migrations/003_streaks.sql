-- Геймификация: серия дней подряд с повторением и имя для рейтинга.
-- XP отдельно не хранится — это число строк в reviews.

alter table users
  -- Имя из initData мини-аппа: рейтинг показывает людей, а не tg_id.
  add column name        text,
  add column streak      int not null default 0,
  add column best_streak int not null default 0,
  -- Последний день (по TZ) с хотя бы одним повторением. Серия жива,
  -- пока он не раньше вчерашнего.
  add column last_day    date;

-- Под недельный рейтинг: повторения с понедельника.
create index reviews_time_idx on reviews (reviewed_at);
