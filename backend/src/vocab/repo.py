"""Весь SQL проекта. Наружу отдаёт asyncpg.Record — плоские строки без логики."""

import json
from typing import Any

import asyncpg

# Карточка = личное расписание + общее содержимое слова. Список колонок
# явный, чтобы select * не начал утекать в ответ API с новой колонкой.
CARD_SELECT = """
    select c.id, w.id as word_id, w.lemma as word, w.translation, w.ipa, w.pos, w.forms,
           w.irregular, w.examples, w.zipf, w.level, w.deck, w.topic,
           (select count(*) from cards l where l.word_id = w.id) as learners,
           exists (select 1 from words o where o.lemma = w.lemma and o.id <> w.id) as homonym,
           c.state, c.step, c.stability, c.difficulty, c.due, c.last_review
    from cards c join words w on w.id = c.word_id
"""

# Неправильные глаголы — набор без поля deck: у слова один набор, а 134
# из них уже в «B1 3000 words». Поэтому набор задан условием, а не меткой.
IRREGULAR_DECK = "Неправильные глаголы"
IRREGULAR_VERB = "w.irregular and w.pos = 'verb' and w.forms like '% · % · %'"

WORD_COLUMNS = "id, lemma, translation, ipa, pos, forms, irregular, examples, zipf, level, banned"

# 10 очков за каждое повторение, как в Duolingo — за урок.
XP_PER_REVIEW = 10

# Серия после сегодняшнего повторения: сегодня уже было — та же, вчера
# было — +1, иначе начинается заново. $2 — часовой пояс.
NEW_STREAK = """
    case when last_day = (now() at time zone $2)::date then streak
         when last_day = (now() at time zone $2)::date - 1 then streak + 1
         else 1 end
"""

# Показываемая серия: пропущенный день обнуляет её сразу, не дожидаясь
# следующего повторения, которое обнулит её в базе.
LIVE_STREAK = """
    case when u.last_day >= (now() at time zone $1)::date - 1 then u.streak else 0 end
"""

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


async def ensure_user(conn: asyncpg.Connection, tg_id: int, name: str | None) -> int:
    # do update вместо do nothing: do nothing ничего не возвращает,
    # и на существующем пользователе пришлось бы делать второй запрос.
    # Имя знает только мини-апп; запрос от бота (name = None) его не стирает.
    return await conn.fetchval(
        "insert into users (tg_id, name) values ($1, $2)"
        " on conflict (tg_id) do update set name = coalesce(excluded.name, users.name)"
        " returning id",
        tg_id,
        name,
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
    """Основное значение леммы: то, что попало в словарь первым."""
    senses = await get_senses(conn, lemma)
    return senses[0] if senses else None


async def get_senses(conn: asyncpg.Connection, lemma: str) -> list[asyncpg.Record]:
    """Все части речи леммы: book — noun «книга» и verb «бронировать».
    Порядок по id: основное значение первым."""
    return await conn.fetch(
        f"select {WORD_COLUMNS} from words where lemma = $1 order by id", lemma
    )


async def save_word(
    conn: asyncpg.Connection, lemma: str, zipf: float, fields: dict[str, Any]
) -> asyncpg.Record:
    # do update: двое прислали одно новое слово одновременно — оба ответа
    # модели годятся, побеждает последний, а ошибки ни у кого нет.
    return await conn.fetchrow(
        f"insert into words (lemma, zipf, translation, ipa, pos, forms, irregular, examples, level)"
        f" values ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
        f" on conflict (lemma, pos) do update set"
        f"  translation = excluded.translation, ipa = excluded.ipa,"
        f"  forms = excluded.forms, irregular = excluded.irregular,"
        f"  examples = excluded.examples, level = excluded.level"
        f" returning {WORD_COLUMNS}",
        lemma,
        zipf,
        fields["translation"],
        fields["ipa"],
        fields["pos"],
        fields["forms"],
        fields["irregular"],
        fields["examples"],
        fields["level"],
    )


async def top_words(
    conn: asyncpg.Connection, user_id: int, limit: int
) -> list[asyncpg.Record]:
    """Рейтинг общего словаря — тот же порядок, что у выдачи новых слов."""
    return await conn.fetch(
        """
        select w.lemma as word, w.translation, w.zipf, w.level,
               count(c.id) as learners,
               bool_or(c.user_id = $1) is true as mine
        from words w left join cards c on c.word_id = w.id
        where not w.banned
        group by w.id
        order by learners desc, w.zipf desc, w.id
        limit $2
        """,
        user_id,
        limit,
    )


async def words_without_zipf(conn: asyncpg.Connection) -> list[str]:
    # Фразы без оценки здесь не исправить — их частоту знает только модель.
    rows = await conn.fetch(
        "select distinct lemma from words where zipf = 0 and lemma not like '% %'"
    )
    return [r["lemma"] for r in rows]


async def set_zipf(conn: asyncpg.Connection, lemma: str, zipf: float) -> None:
    await conn.execute("update words set zipf = $2 where lemma = $1", lemma, zipf)


async def ban_word(conn: asyncpg.Connection, lemma: str) -> bool:
    # Все части речи леммы разом: у book их может быть две, и тогда тег
    # «UPDATE 2» — тоже успех.
    tag = await conn.execute("update words set banned = true where lemma = $1", lemma)
    await conn.execute(
        "update reports set resolved_at = now() where resolved_at is null"
        " and word_id in (select id from words where lemma = $1)",
        lemma,
    )
    return tag != "UPDATE 0"


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


async def has_card(conn: asyncpg.Connection, user_id: int, word_id: int) -> bool:
    return await conn.fetchval(
        "select exists(select 1 from cards where user_id = $1 and word_id = $2)",
        user_id,
        word_id,
    )


async def word_exists(conn: asyncpg.Connection, word_id: int) -> bool:
    return await conn.fetchval(
        "select exists(select 1 from words where id = $1 and not banned)", word_id
    )


async def discover(
    conn: asyncpg.Connection, user_id: int, limit: int, deck: str | None = None
) -> list[asyncpg.Record]:
    """Берёт из общего словаря слова, которых у пользователя нет, и сразу
    заводит на них карточки: сначала наборы учителя в порядке файла
    (B1 3000 words, потом глаголы с предлогами), затем знаменательные,
    среди них — уровень A1 раньше A2, внутри уровня — те, что учат больше
    людей, потом самые частые в языке.

    Пока пользователей мало, популярность у всех одинаковая и порядок
    фактически задаёт частота. С deck — только из этого набора.
    """
    ids = await conn.fetch(
        f"""
        insert into cards (user_id, word_id)
        select $1, w.id from words w
        where not w.banned
          and not exists (select 1 from cards c where c.user_id = $1 and c.word_id = w.id)
          and ($3::text is null or w.deck = $3 or ($3 = $4 and {IRREGULAR_VERB}))
        -- Неправильные глаголы — по частоте: be, have, do раньше forsake.
        -- Служебные слова в конец: the, of, you знает любой начинающий, и
        -- первая же выдача из них отбила бы желание продолжать.
        order by case when $3 = $4 then w.zipf end desc nulls last,
                 w.deck_order nulls last,
                 w.pos in ('determiner', 'preposition', 'pronoun', 'conjunction',
                           'modal', 'interjection', 'numeral', 'article', 'particle'),
                 w.level nulls last,
                 (select count(*) from cards c where c.word_id = w.id) desc,
                 w.zipf desc, w.id
        limit $2
        on conflict do nothing
        returning id
        """,
        user_id,
        limit,
        deck,
        IRREGULAR_DECK,
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
        f"{CARD_SELECT} where c.user_id = $1 and not w.banned and c.known_at is null"
        f" and c.due <= now() order by c.due limit $2",
        user_id,
        limit,
    )


async def apply_review(
    conn: asyncpg.Connection,
    user_id: int,
    card_id: int,
    rating: int,
    fsrs: dict[str, Any],
    tz: str,
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
        await touch_streak(conn, user_id, tz)


async def set_known(conn: asyncpg.Connection, user_id: int, card_id: int, known: bool) -> bool:
    """Ставит или снимает «знаю». False — карточки нет или она чужая."""
    result = await conn.execute(
        "update cards set known_at = case when $3 then now() end"
        " where id = $1 and user_id = $2",
        card_id,
        user_id,
        known,
    )
    return result != "UPDATE 0"


async def touch_streak(conn: asyncpg.Connection, user_id: int, tz: str) -> None:
    """Сегодня было занятие: повторение слова или задание тетради."""
    await conn.execute(
        f"update users set streak = {NEW_STREAK},"
        f" best_streak = greatest(best_streak, {NEW_STREAK}),"
        f" last_day = (now() at time zone $2)::date"
        f" where id = $1",
        user_id,
        tz,
    )


async def stats(conn: asyncpg.Connection, user_id: int, tz: str) -> asyncpg.Record:
    """Сводка одним запросом.

    «Выучено» — карточки в состоянии Review (state = 2): из обучения они
    вышли, шаги пройдены. Плюс отмеченные «знаю»: их не повторяют вовсе. Порог по stability сюда не годится — он зависит
    от параметров FSRS и менялся бы при их дообучении.
    """
    return await conn.fetchrow(
        f"""
        select
          count(*)                                   as total,
          count(*) filter (where c.state = 2 or c.known_at is not null) as learned,
          count(*) filter (where c.known_at is null and c.due <= now()) as due_now,
          count(*) filter (
            where c.known_at is null
              and c.due < (date_trunc('day', now() at time zone $2) + interval '1 day')
                          at time zone $2
          )                                          as due_today
        from {USER_CARDS}
        """,
        user_id,
        tz,
    )


LEARNED = "count(c.id) filter (where c.state = 2 or c.known_at is not null)"


async def deck_progress(conn: asyncpg.Connection, user_id: int) -> list[asyncpg.Record]:
    """Сколько слов каждого набора выучено: Review или «знаю», как в stats."""
    return await conn.fetch(
        f"""
        select deck, total, learned from (
          select w.deck, count(*) as total, {LEARNED} as learned, min(w.deck_order) as position
          from words w
          left join cards c on c.word_id = w.id and c.user_id = $1
          where w.deck is not null and not w.banned
          group by w.deck
          union all
          select $2::text, count(*), {LEARNED}, null
          from words w
          left join cards c on c.word_id = w.id and c.user_id = $1
          where {IRREGULAR_VERB} and not w.banned
        ) decks
        order by position nulls last
        """,
        user_id,
        IRREGULAR_DECK,
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
        due as (
          select (c.due at time zone $2)::date as day from {USER_CARDS} and c.known_at is null
        )
        select days.day, count(due.day) as count
        from days left join due on due.day = days.day
        group by days.day
        order by days.day
        """,
        user_id,
        tz,
        days,
    )


async def streak(conn: asyncpg.Connection, user_id: int, tz: str) -> asyncpg.Record:
    return await conn.fetchrow(
        f"select {LIVE_STREAK} as streak, u.best_streak from users u where u.id = $2",
        tz,
        user_id,
    )


async def leaderboard(conn: asyncpg.Connection, tz: str) -> list[asyncpg.Record]:
    """XP за текущую неделю с понедельника — у всех, кто на ней занимался.

    Неделя, а не всё время: иначе первые пользователи навсегда заняли бы
    верх, и новичку не за что было бы бороться.
    """
    # Решённое задание тетради стоит столько же, сколько повторение слова:
    # иначе ученики, которые только делают грамматику, в рейтинг не попали бы.
    return await conn.fetch(
        f"""
        with week as (select date_trunc('week', now() at time zone $1) at time zone $1 as start),
        activity as (
          select c.user_id from reviews r join cards c on c.id = r.card_id, week
          where r.reviewed_at >= week.start
          union all
          select g.user_id from grammar_results g, week where g.updated_at >= week.start
        )
        select u.id as user_id, coalesce(u.name, 'Без имени') as name,
               count(*) * {XP_PER_REVIEW} as xp,
               {LIVE_STREAK} as streak,
               rank() over (order by count(*) desc) as place
        from activity a
        join users u on u.id = a.user_id
        group by u.id
        order by place, u.id
        """,
        tz,
    )


async def reminder_targets(conn: asyncpg.Connection, tz: str) -> list[asyncpg.Record]:
    """Кому может понадобиться напоминание: у кого есть слова и кто сегодня
    ещё не занимался. Что именно сказать (или промолчать), решает бот.

    gap — сколько дней назад было последнее повторение; null — не было ни разу.
    """
    return await conn.fetch(
        """
        select u.tg_id, u.streak,
               (now() at time zone $1)::date - u.last_day as gap,
               count(c.id) filter (
                 where c.due <= now() and not w.banned and c.known_at is null
               ) as due
        from users u
        join cards c on c.user_id = u.id
        join words w on w.id = c.word_id
        where u.last_day is null or u.last_day < (now() at time zone $1)::date
        group by u.id
        """,
        tz,
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


# Для тестов годятся только слова, которые уже видели: угадывать перевод
# слова, которого не знаешь, — не проверка, а лотерея. Исключение —
# неправильные глаголы: формы учат таблицей, их можно спрашивать сразу.
QUIZ_FILTERS = {
    "any": "c.last_review is not null",
    "irregular": IRREGULAR_VERB,
}


async def quiz_cards(
    conn: asyncpg.Connection, user_id: int, mode: str, limit: int
) -> list[asyncpg.Record]:
    """Сначала то, что пора повторять, потом то, что подойдёт раньше всего:
    тест засчитывается как повторение, и раньше срока FSRS это учитывает."""
    return await conn.fetch(
        f"{CARD_SELECT} where c.user_id = $1 and not w.banned and c.known_at is null"
        f" and {QUIZ_FILTERS[mode]}"
        f" order by c.due limit $2",
        user_id,
        limit,
    )


async def distractors(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    """Случайные слова общего словаря — неправильные варианты ответа. Свои
    слова не исключаются: путать знакомые между собой — лучшая проверка,
    а сам ответ quiz.choices отсеивает."""
    return await conn.fetch(
        "select lemma, translation, pos from words where not banned order by random() limit $1",
        limit,
    )


async def report(
    conn: asyncpg.Connection, user_id: int, word_id: int, reason: str, comment: str | None
) -> bool:
    """Жалоба на слово. False — такого слова нет."""
    if not await conn.fetchval("select exists (select 1 from words where id = $1)", word_id):
        return False
    await conn.execute(
        "insert into reports (word_id, user_id, reason, comment) values ($1, $2, $3, $4)"
        " on conflict (word_id, user_id) where resolved_at is null"
        " do update set reason = excluded.reason, comment = excluded.comment,"
        "  created_at = now()",
        word_id,
        user_id,
        reason,
        comment,
    )
    return True


async def open_reports(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    """Слова с открытыми жалобами: самые обсуждаемые первыми."""
    return await conn.fetch(
        f"""
        select {", ".join("w." + c for c in WORD_COLUMNS.split(", "))},
               count(*) as reports,
               array_agg(distinct r.reason) as reasons,
               array_remove(array_agg(r.comment order by r.created_at desc), null) as comments,
               max(r.created_at) as last_at
        from reports r join words w on w.id = r.word_id
        where r.resolved_at is null
        group by w.id
        order by reports desc, last_at desc
        """
    )


async def resolve_reports(conn: asyncpg.Connection, word_id: int) -> None:
    await conn.execute(
        "update reports set resolved_at = now() where word_id = $1 and resolved_at is null",
        word_id,
    )


async def admin_words(conn: asyncpg.Connection, query: str, limit: int) -> list[asyncpg.Record]:
    """Поиск по всему словарю, вместе с заблокированными. Совпадение
    с начала слова выше, чем в середине."""
    return await conn.fetch(
        f"select {WORD_COLUMNS} from words where lemma like $1"
        f" order by lemma not like $2, lemma, id limit $3",
        f"%{query}%",
        f"{query}%",
        limit,
    )


async def update_word(
    conn: asyncpg.Connection, word_id: int, fields: dict[str, Any]
) -> asyncpg.Record | None:
    """Правка слова админом. Любое решение по слову закрывает жалобы на него:
    и исправление, и блокировка — это ответ на них."""
    async with conn.transaction():
        row = await conn.fetchrow(
            f"update words set translation = $2, ipa = $3, forms = $4, irregular = $5,"
            f" examples = $6, level = $7, banned = $8 where id = $1"
            f" returning {WORD_COLUMNS}",
            word_id,
            fields["translation"],
            fields["ipa"],
            fields["forms"],
            fields["irregular"],
            fields["examples"],
            fields["level"],
            fields["banned"],
        )
        if row is not None:
            await resolve_reports(conn, word_id)
    return row


async def admin_summary(conn: asyncpg.Connection) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        select
          (select count(*) from users)                                  as users,
          (select count(distinct c.user_id) from reviews r join cards c on c.id = r.card_id
            where r.reviewed_at > now() - interval '7 days')            as active_week,
          (select count(*) from words where not banned)                 as words,
          (select count(*) from words where banned)                     as banned,
          (select count(distinct word_id) from reports where resolved_at is null) as open_reports
        """
    )


# --- тетрадь ------------------------------------------------------------------


async def grammar_results(conn: asyncpg.Connection, user_id: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select item, clean, was_wrong, answers from grammar_results where user_id = $1",
        user_id,
    )


async def grammar_accepted(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    """Ответы, засчитанные учителями: движок мини-аппа принимает их наравне с ключом."""
    return await conn.fetch("select item, slot, answer from grammar_accepted")


async def save_grammar_attempt(
    conn: asyncpg.Connection,
    user_id: int,
    item: str,
    clean: bool,
    answers: list[str],
    mistakes: list[tuple[int, str, str]],
    tz: str,
) -> None:
    """Итог задания, его ошибки и серия — одной транзакцией: ошибки без
    итога учитель увидел бы у задания, которого ученик будто не решал."""
    async with conn.transaction():
        await conn.execute(
            """
            insert into grammar_results (user_id, item, clean, was_wrong, answers)
            values ($1, $2, $3, not $3, $4)
            on conflict (user_id, item) do update set
              clean = excluded.clean,
              was_wrong = grammar_results.was_wrong or excluded.was_wrong,
              answers = excluded.answers,
              updated_at = now()
            """,
            user_id, item, clean, answers,
        )
        if mistakes:
            await conn.executemany(
                "insert into grammar_mistakes (user_id, item, slot, answer, why)"
                " values ($1, $2, $3, $4, $5)",
                [(user_id, item, slot, answer, why) for slot, answer, why in mistakes],
            )
        await touch_streak(conn, user_id, tz)


async def import_grammar(
    conn: asyncpg.Connection, user_id: int, rows: list[tuple[str, bool, bool, list[str]]]
) -> int:
    """Перенос из CloudStorage. Уже решённое в базе не перетирается:
    база новее любого локального хранилища."""
    if not rows:
        return 0
    # Ответы идут JSON-строками: список списков asyncpg передал бы как
    # двумерный массив, и unnest разложил бы его не по заданиям.
    result = await conn.fetch(
        """
        insert into grammar_results (user_id, item, clean, was_wrong, answers)
        select $1, r.item, r.clean, r.was_wrong, r.answers::jsonb
        from unnest($2::text[], $3::bool[], $4::bool[], $5::text[])
             as r(item, clean, was_wrong, answers)
        on conflict (user_id, item) do nothing
        returning item
        """,
        user_id,
        [r[0] for r in rows],
        [r[1] for r in rows],
        [r[2] for r in rows],
        [json.dumps(r[3], ensure_ascii=False) for r in rows],
    )
    return len(result)


async def is_teacher(conn: asyncpg.Connection, user_id: int) -> bool:
    return bool(await conn.fetchval("select is_teacher from users where id = $1", user_id))


async def teachers(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select id as user_id, tg_id, coalesce(name, 'Без имени') as name"
        " from users where is_teacher order by name"
    )


async def remove_teacher(conn: asyncpg.Connection, user_id: int) -> bool:
    status = await conn.execute(
        "update users set is_teacher = false where id = $1 and is_teacher", user_id
    )
    return status != "UPDATE 0"


async def create_teacher_invite(conn: asyncpg.Connection, user_id: int, code: str) -> None:
    await conn.execute(
        "insert into teacher_invites (code, created_by) values ($1, $2)", code, user_id
    )


async def redeem_teacher_invite(
    conn: asyncpg.Connection, code: str, user_id: int, ttl_days: int
) -> asyncpg.Record | None:
    """Гасит приглашение и делает учителем. None — ссылки нет, она занята или
    просрочена. Возвращает tg_id того, кто приглашал: бот ему сообщит."""
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            update teacher_invites set used_by = $2, used_at = now()
            where code = $1 and used_by is null
              and created_at > now() - make_interval(days => $3)
            returning (select tg_id from users where id = created_by) as inviter_tg_id
            """,
            code, user_id, ttl_days,
        )
        if row is not None:
            await conn.execute("update users set is_teacher = true where id = $1", user_id)
    return row


async def students(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    """Все, кто делал тетрадь, со сводкой. Неразобранные ошибки — те, что
    учитель ещё не засчитал, — вверху: с них учитель и начинает."""
    return await conn.fetch(
        """
        with r as (
          select user_id, count(*) as done,
                 count(*) filter (where clean and not was_wrong) as first_try,
                 count(*) filter (where not clean) as wrong_now,
                 max(updated_at) as last_at
          from grammar_results group by user_id
        ),
        m as (
          select user_id, count(*) as mistakes,
                 count(*) filter (where created_at > now() - interval '7 days') as mistakes_week
          from grammar_mistakes where accepted_by is null group by user_id
        )
        select u.id as user_id, coalesce(u.name, 'Без имени') as name,
               coalesce(r.done, 0) as done, coalesce(r.first_try, 0) as first_try,
               coalesce(r.wrong_now, 0) as wrong_now,
               coalesce(m.mistakes, 0) as mistakes, coalesce(m.mistakes_week, 0) as mistakes_week,
               r.last_at
        from r join users u on u.id = r.user_id
        left join m on m.user_id = r.user_id
        order by r.last_at desc nulls last
        """
    )


async def student(conn: asyncpg.Connection, user_id: int) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "select id as user_id, coalesce(name, 'Без имени') as name from users where id = $1",
        user_id,
    )


async def student_results(conn: asyncpg.Connection, user_id: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select item, clean, was_wrong, answers, updated_at from grammar_results"
        " where user_id = $1 order by updated_at desc",
        user_id,
    )


async def student_mistakes(conn: asyncpg.Connection, user_id: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select id, item, slot, answer, why, created_at, accepted_by is not null as accepted"
        " from grammar_mistakes where user_id = $1 order by created_at desc limit 500",
        user_id,
    )


async def accept_mistake(
    conn: asyncpg.Connection, mistake_id: int, teacher_id: int
) -> asyncpg.Record | None:
    """Ответ ученика верный, ключ его не знал. Ответ становится принятым
    у всех, а у этого ученика задание перестаёт считаться ошибкой, если
    неразобранных ошибок в нём больше нет."""
    async with conn.transaction():
        row = await conn.fetchrow(
            "update grammar_mistakes set accepted_by = $2 where id = $1"
            " returning user_id, item, slot, answer",
            mistake_id, teacher_id,
        )
        if row is None:
            return None
        await conn.execute(
            "insert into grammar_accepted (item, slot, answer, added_by) values ($1, $2, $3, $4)"
            " on conflict do nothing",
            row["item"], row["slot"], row["answer"].strip(), teacher_id,
        )
        # Та же ошибка у других учеников тоже засчитывается: ответ теперь верный.
        await conn.execute(
            "update grammar_mistakes set accepted_by = $4"
            " where item = $1 and slot = $2 and lower(trim(answer)) = lower(trim($3))"
            " and accepted_by is null",
            row["item"], row["slot"], row["answer"], teacher_id,
        )
        await conn.execute(
            """
            update grammar_results g set clean = true
            where g.item = $1 and not g.clean and not exists (
              select 1 from grammar_mistakes m
              where m.user_id = g.user_id and m.item = g.item and m.accepted_by is null
            )
            """,
            row["item"],
        )
    return row


async def common_mistakes(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    """Где ошибаются чаще всего — по числу учеников, а не попыток: один
    упрямый ученик не должен заслонять задание, на котором сыплется класс."""
    return await conn.fetch(
        """
        select item, count(distinct user_id) as students, count(*) as attempts,
               (array_agg(answer order by created_at desc))[1:5] as answers
        from grammar_mistakes where accepted_by is null
        group by item
        order by students desc, attempts desc
        limit $1
        """,
        limit,
    )


async def grammar_summary(conn: asyncpg.Connection, user_id: int) -> asyncpg.Record:
    return await conn.fetchrow(
        "select count(*) as done, count(*) filter (where not clean) as wrong_now"
        " from grammar_results where user_id = $1",
        user_id,
    )
