"""Весь SQL проекта. Наружу отдаёт asyncpg.Record — плоские строки без логики."""

import json
from typing import Any

import asyncpg

# Карточка = личное расписание + общее содержимое слова. Список колонок
# явный, чтобы select * не начал утекать в ответ API с новой колонкой.
CARD_SELECT = """
    select c.id, w.lemma as word, w.translation, w.ipa, w.pos, w.forms,
           w.irregular, w.examples,
           c.state, c.step, c.stability, c.difficulty, c.due, c.last_review
    from cards c join words w on w.id = c.word_id
"""

WORD_COLUMNS = "id, lemma, translation, ipa, pos, forms, irregular, examples, zipf, banned"

# Заблокированное слово пропадает из всех личных очередей и счётчиков.
USER_CARDS = "cards c join words w on w.id = c.word_id where c.user_id = $1 and not w.banned"


def normalize_word(word: str) -> str:
    """Схлопывает пробелы и регистр: «Resilient» и «resilient» — одно слово."""
    return " ".join(word.split()).lower()


async def init_connection(conn: asyncpg.Connection) -> None:
    # Без кодека asyncpg отдаёт jsonb строкой, и examples уехали бы
    # в ответ API экранированным текстом.
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def ensure_user(conn: asyncpg.Connection, tg_id: int) -> int:
    # do update вместо do nothing: do nothing ничего не возвращает,
    # и на существующем пользователе пришлось бы делать второй запрос.
    return await conn.fetchval(
        "insert into users (tg_id) values ($1)"
        " on conflict (tg_id) do update set tg_id = excluded.tg_id"
        " returning id",
        tg_id,
    )


async def spend_llm(conn: asyncpg.Connection, user_id: int, tz: str) -> int:
    """Учитывает запрос к ИИ и возвращает, сколько их сегодня с этим."""
    return await conn.fetchval(
        "update users set"
        " llm_used = case when llm_day = (now() at time zone $2)::date"
        "                 then llm_used + 1 else 1 end,"
        " llm_day = (now() at time zone $2)::date"
        " where id = $1 returning llm_used",
        user_id,
        tz,
    )


async def get_word(conn: asyncpg.Connection, lemma: str) -> asyncpg.Record | None:
    return await conn.fetchrow(f"select {WORD_COLUMNS} from words where lemma = $1", lemma)


async def save_word(
    conn: asyncpg.Connection, lemma: str, zipf: float, fields: dict[str, Any]
) -> asyncpg.Record:
    # do update: двое прислали одно новое слово одновременно — оба ответа
    # модели годятся, побеждает последний, а ошибки ни у кого нет.
    return await conn.fetchrow(
        f"insert into words (lemma, zipf, translation, ipa, pos, forms, irregular, examples)"
        f" values ($1, $2, $3, $4, $5, $6, $7, $8)"
        f" on conflict (lemma) do update set"
        f"  translation = excluded.translation, ipa = excluded.ipa, pos = excluded.pos,"
        f"  forms = excluded.forms, irregular = excluded.irregular,"
        f"  examples = excluded.examples"
        f" returning {WORD_COLUMNS}",
        lemma,
        zipf,
        fields["translation"],
        fields["ipa"],
        fields["pos"],
        fields["forms"],
        fields["irregular"],
        fields["examples"],
    )


async def ban_word(conn: asyncpg.Connection, lemma: str) -> bool:
    tag = await conn.execute("update words set banned = true where lemma = $1", lemma)
    return tag.endswith(" 1")


async def learners(conn: asyncpg.Connection, word_id: int) -> int:
    return await conn.fetchval("select count(*) from cards where word_id = $1", word_id)


async def add_card(conn: asyncpg.Connection, user_id: int, word_id: int) -> bool:
    """Заводит карточку. False — слово у пользователя уже было."""
    card_id = await conn.fetchval(
        "insert into cards (user_id, word_id) values ($1, $2)"
        " on conflict (user_id, word_id) do nothing returning id",
        user_id,
        word_id,
    )
    return card_id is not None


async def discover(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    """Берёт из общего словаря слова, которых у пользователя нет, и сразу
    заводит на них карточки: сначала те, что учат больше людей, потом
    самые частые в языке.

    Пока пользователей мало, популярность у всех одинаковая и порядок
    фактически задаёт частота.
    """
    ids = await conn.fetch(
        """
        insert into cards (user_id, word_id)
        select $1, w.id from words w
        where not w.banned
          and not exists (select 1 from cards c where c.user_id = $1 and c.word_id = w.id)
        order by (select count(*) from cards c where c.word_id = w.id) desc,
                 w.zipf desc, w.id
        limit $2
        on conflict do nothing
        returning id
        """,
        user_id,
        limit,
    )
    # array_position сохраняет порядок выборки выше: популярные слова первыми.
    return await conn.fetch(
        f"{CARD_SELECT} where c.id = any($1::bigint[]) order by array_position($1::bigint[], c.id)",
        [r["id"] for r in ids],
    )


async def get_card(
    conn: asyncpg.Connection, user_id: int, card_id: int
) -> asyncpg.Record | None:
    # user_id в условии, а не только в проверке после выборки: иначе чужая
    # карточка утекала бы уже самим фактом ответа 200.
    return await conn.fetchrow(
        f"{CARD_SELECT} where c.id = $1 and c.user_id = $2", card_id, user_id
    )


async def queue(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"{CARD_SELECT} where c.user_id = $1 and not w.banned and c.due <= now()"
        f" order by c.due limit $2",
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


async def stats(conn: asyncpg.Connection, user_id: int, tz: str) -> asyncpg.Record:
    """Сводка одним запросом.

    «Выучено» — карточки в состоянии Review (state = 2): из обучения они
    вышли, шаги пройдены. Порог по stability сюда не годится — он зависит
    от параметров FSRS и менялся бы при их дообучении.
    """
    return await conn.fetchrow(
        f"""
        select
          count(*)                                   as total,
          count(*) filter (where c.state = 2)        as learned,
          count(*) filter (where c.due <= now())     as due_now,
          count(*) filter (
            where c.due < (date_trunc('day', now() at time zone $2) + interval '1 day')
                          at time zone $2
          )                                          as due_today
        from {USER_CARDS}
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
        f"""
        with days as (
          select generate_series(
            date_trunc('day', now() at time zone $2),
            date_trunc('day', now() at time zone $2) + make_interval(days => $3 - 1),
            interval '1 day'
          )::date as day
        ),
        due as (select (c.due at time zone $2)::date as day from {USER_CARDS})
        select days.day, count(due.day) as count
        from days left join due on due.day = days.day
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
        "select u.tg_id, count(*) as due"
        " from users u join cards c on c.user_id = u.id join words w on w.id = c.word_id"
        " where not w.banned and c.due <= now()"
        " group by u.tg_id"
    )


async def search(
    conn: asyncpg.Connection, user_id: int, query: str, limit: int
) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"select c.id, w.lemma as word, w.translation, c.due from {USER_CARDS}"
        f" and w.lemma like $2 order by w.lemma limit $3",
        user_id,
        f"%{normalize_word(query)}%",
        limit,
    )


async def weak_cards(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    """Карточки с наибольшим числом провалов (rating = 1, Again)."""
    return await conn.fetch(
        "select c.id, w.lemma as word, w.translation, w.examples, count(*) as lapses"
        " from cards c"
        " join words w on w.id = c.word_id"
        " join reviews r on r.card_id = c.id and r.rating = 1"
        " where c.user_id = $1 and not w.banned"
        " group by c.id, w.lemma, w.translation, w.examples"
        " order by lapses desc, w.lemma limit $2",
        user_id,
        limit,
    )
