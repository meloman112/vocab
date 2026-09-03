"""Весь SQL проекта. Наружу отдаёт asyncpg.Record — плоские строки без логики."""

from typing import Any

import asyncpg

# Список колонок вынесен, чтобы select * не начал утекать в ответ API,
# когда в cards появится новая техническая колонка.
CARD_COLUMNS = """
    id, word, status, translation, ipa, pos, example, example_ru, source_url,
    state, step, stability, difficulty, due, last_review, created_at
"""


def normalize_word(word: str) -> str:
    """Схлопывает пробелы и регистр: одно слово — одна карточка.

    Регистр теряется намеренно. Иначе выделенное в начале предложения
    «Resilient» и встреченное позже «resilient» стали бы двумя карточками.
    """
    return " ".join(word.split()).lower()


async def ensure_user(conn: asyncpg.Connection, tg_id: int) -> int:
    # do update вместо do nothing: do nothing ничего не возвращает,
    # и на существующем пользователе пришлось бы делать второй запрос.
    return await conn.fetchval(
        "insert into users (tg_id) values ($1)"
        " on conflict (tg_id) do update set tg_id = excluded.tg_id"
        " returning id",
        tg_id,
    )


async def add_card(
    conn: asyncpg.Connection, user_id: int, word: str, source_url: str | None
) -> tuple[asyncpg.Record, bool]:
    """Создаёт карточку. Второй элемент — была ли она создана сейчас."""
    row = await conn.fetchrow(
        f"insert into cards (user_id, word, source_url) values ($1, $2, $3)"
        f" on conflict (user_id, word) do nothing"
        f" returning {CARD_COLUMNS}",
        user_id,
        word,
        source_url,
    )
    if row is not None:
        return row, True

    existing = await conn.fetchrow(
        f"select {CARD_COLUMNS} from cards where user_id = $1 and word = $2",
        user_id,
        word,
    )
    return existing, False


async def get_card(
    conn: asyncpg.Connection, user_id: int, card_id: int
) -> asyncpg.Record | None:
    # user_id в условии, а не только в проверке после выборки: иначе чужая
    # карточка утекала бы уже самим фактом ответа 200.
    return await conn.fetchrow(
        f"select {CARD_COLUMNS} from cards where id = $1 and user_id = $2",
        card_id,
        user_id,
    )


async def queue(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"select {CARD_COLUMNS} from cards"
        f" where user_id = $1 and status = 'ready' and due <= now()"
        f" order by due limit $2",
        user_id,
        limit,
    )


async def apply_review(
    conn: asyncpg.Connection, card_id: int, rating: int, fsrs: dict[str, Any]
) -> None:
    """Пишет оценку и новое расписание одной транзакцией.

    Порядок важен: без транзакции падение между UPDATE и INSERT дало бы
    сдвинутое расписание без записи в истории, и Optimizer позже обучался
    бы на неполных данных.
    """
    async with conn.transaction():
        await conn.execute(
            "update cards set state = $2, step = $3, stability = $4,"
            " difficulty = $5, due = $6, last_review = $7 where id = $1",
            card_id,
            fsrs["state"],
            fsrs["step"],
            fsrs["stability"],
            fsrs["difficulty"],
            fsrs["due"],
            fsrs["last_review"],
        )
        await conn.execute(
            "insert into reviews (card_id, rating) values ($1, $2)", card_id, rating
        )


async def set_enrichment(
    conn: asyncpg.Connection, card_id: int, fields: dict[str, str]
) -> None:
    await conn.execute(
        "update cards set status = 'ready', translation = $2, ipa = $3,"
        " pos = $4, example = $5, example_ru = $6 where id = $1",
        card_id,
        fields["translation"],
        fields["ipa"],
        fields["pos"],
        fields["example"],
        fields["example_ru"],
    )


async def mark_failed(conn: asyncpg.Connection, card_id: int) -> None:
    await conn.execute("update cards set status = 'failed' where id = $1", card_id)


async def mark_pending(conn: asyncpg.Connection, user_id: int, card_id: int) -> bool:
    """Возвращает карточку в очередь на обогащение. False — карточки нет."""
    status = await conn.fetchval(
        "update cards set status = 'pending' where id = $1 and user_id = $2"
        " returning status",
        card_id,
        user_id,
    )
    return status is not None


async def failed_cards(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select id, word from cards where user_id = $1 and status = 'failed'"
        " order by created_at desc limit $2",
        user_id,
        limit,
    )


async def delete_card(conn: asyncpg.Connection, user_id: int, card_id: int) -> bool:
    tag = await conn.execute(
        "delete from cards where id = $1 and user_id = $2", card_id, user_id
    )
    return tag.endswith(" 1")


async def stats(conn: asyncpg.Connection, user_id: int, tz: str) -> asyncpg.Record:
    """Сводка одним запросом.

    «Выучено» — карточки в состоянии Review (state = 2): из обучения они
    вышли, шаги пройдены. Порог по stability сюда не годится — он зависит
    от параметров FSRS и менялся бы при их дообучении.
    """
    return await conn.fetchrow(
        """
        select
          count(*)                                                   as total,
          count(*) filter (where status = 'ready' and state = 2)      as learned,
          count(*) filter (where status = 'pending')                  as pending,
          count(*) filter (where status = 'failed')                   as failed,
          count(*) filter (where status = 'ready' and due <= now())   as due_now,
          count(*) filter (
            where status = 'ready'
              and due < (date_trunc('day', now() at time zone $2) + interval '1 day')
                        at time zone $2
          )                                                           as due_today
        from cards where user_id = $1
        """,
        user_id,
        tz,
    )


async def forecast(
    conn: asyncpg.Connection, user_id: int, tz: str, days: int
) -> list[asyncpg.Record]:
    """Сколько карточек придёт на повторение в каждый из следующих days дней.

    generate_series, а не группировка по факту: дни без повторений обязаны
    попасть в ответ нулями, иначе график на фронте съедет.
    """
    return await conn.fetch(
        """
        with days as (
          select generate_series(
            date_trunc('day', now() at time zone $2),
            date_trunc('day', now() at time zone $2) + make_interval(days => $3 - 1),
            interval '1 day'
          )::date as day
        )
        select days.day,
               count(c.id) as count
        from days
        left join cards c
          on c.user_id = $1
         and c.status = 'ready'
         and (c.due at time zone $2)::date = days.day
        group by days.day
        order by days.day
        """,
        user_id,
        tz,
        days,
    )


async def due_by_user(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    """Для напоминаний бота: у кого прямо сейчас есть что повторять."""
    return await conn.fetch(
        "select u.tg_id, count(c.id) as due"
        " from users u join cards c on c.user_id = u.id"
        " where c.status = 'ready' and c.due <= now()"
        " group by u.tg_id having count(c.id) > 0"
    )


async def search(
    conn: asyncpg.Connection, user_id: int, query: str, limit: int
) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select id, word, translation, status, due from cards"
        " where user_id = $1 and word like $2 order by word limit $3",
        user_id,
        f"%{normalize_word(query)}%",
        limit,
    )


async def weak_cards(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    """Карточки с наибольшим числом провалов (rating = 1, Again)."""
    return await conn.fetch(
        "select c.id, c.word, c.translation, c.example,"
        " count(r.id) filter (where r.rating = 1) as lapses"
        " from cards c left join reviews r on r.card_id = c.id"
        " where c.user_id = $1"
        " group by c.id, c.word, c.translation, c.example"
        " having count(r.id) filter (where r.rating = 1) > 0"
        " order by lapses desc, c.word limit $2",
        user_id,
        limit,
    )
