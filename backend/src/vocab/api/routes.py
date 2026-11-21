"""Ручки. Транспортный слой: разбор запроса, вызов repo, сборка DTO."""

import logging
import random
import re
from datetime import UTC, datetime
from html import escape
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from .. import dictionary, enrich, grammar, lexicon, quiz, repo, srs
from ..config import Settings, settings
from . import schemas
from .auth import Identity, admin_user, current_user, identity, service_only

router = APIRouter()
log = logging.getLogger(__name__)

FORECAST_DAYS = 7
# Сколько новых слов из общего словаря выдаётся за одно «Давай».
DISCOVER_LIMIT = 10
# Новых слов в день, считая свои: 41 за день у живого ученика дали четверть
# «не помню» назавтра. 15 — потолок, при котором слова ещё держатся.
NEW_PER_DAY = 15
LEADERBOARD_SIZE = 10
# Глаголов в одной игре: хватает на минуту и влезает в 1 КБ данных виджета.
VERBS_GAME = 12
# Неправильных вариантов с запасом: часть отсеется как синонимы и та же лемма.
DISTRACTOR_POOL = 200
# Пример с формой слова находится не у каждой карточки — берём с запасом.
CLOZE_OVERSAMPLE = 4


@router.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    # Проверка живого соединения с базой, а не только процесса: контейнер,
    # который отвечает 200 без базы, compose считает здоровым напрасно.
    async with request.app.state.pool.acquire() as conn:
        await conn.execute("select 1")
    return {"status": "ok"}


@router.post("/words", response_model=schemas.AddWordOut)
async def add_word(
    body: schemas.AddWord, request: Request, user_id: int = Depends(current_user)
) -> schemas.AddWordOut:
    """Разбирает текст, заводит карточки и сразу отдаёт перевод.

    Ответ ждёт модель, только если слова ещё нет в общем словаре.
    """
    try:
        entries = await dictionary.add_text(
            request.app.state.pool, settings(), user_id, body.word, body.pos, body.as_is
        )
    except dictionary.Misspelled as exc:
        # Отдельно от Rejected: клиенту нужно само исправление, чтобы
        # показать кнопку, а не только текст.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": str(exc), "suggestion": exc.suggestion},
        ) from exc
    except dictionary.Rejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except enrich.EnrichError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "ИИ сейчас не отвечает, пришли слово чуть позже."
        ) from exc
    return schemas.AddWordOut(entries=[schemas.WordEntry(**e) for e in entries])


@router.get("/lookup", response_model=schemas.LookupOut)
async def lookup(
    request: Request,
    text: str = Query(min_length=1, max_length=500),
    user_id: int = Depends(current_user),
) -> schemas.WordLookup | schemas.TextLookup:
    """Перевод выделенного в мини-аппе: слово — карточкой из словаря (без
    заведения карточки у пользователя), предложение — моделью целиком."""
    try:
        entry = await dictionary.lookup(request.app.state.pool, settings(), user_id, text)
    except dictionary.Rejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except enrich.EnrichError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "ИИ сейчас не отвечает, попробуй чуть позже."
        ) from exc
    if entry["kind"] == "text":
        return schemas.TextLookup(**entry)
    return schemas.WordLookup(**entry)


@router.post("/words/{word_id}/card", status_code=status.HTTP_204_NO_CONTENT)
async def save_looked_up(
    word_id: int, request: Request, user_id: int = Depends(current_user)
) -> None:
    """«Добавить в мои слова» под переводом выделенного."""
    async with request.app.state.pool.acquire() as conn:
        if not await repo.word_exists(conn, word_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет такого слова")
        await repo.add_card(conn, user_id, word_id)


def _cards_out(rows) -> schemas.QueueOut:
    return schemas.QueueOut(cards=[
        schemas.CardOut(
            **dict(row),
            top=lexicon.rank_label(row["zipf"], row["level"]),
            remembered_due=srs.review(row, srs.REMEMBERED)["due"],
        )
        for row in quiz.spread(rows)
    ])


@router.get("/queue", response_model=schemas.QueueOut)
async def get_queue(
    request: Request, user_id: int = Depends(current_user)
) -> schemas.QueueOut:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.queue(conn, user_id, settings().queue_limit)
    return _cards_out(rows)


@router.post("/discover", response_model=schemas.QueueOut)
async def discover(
    request: Request, deck: str | None = None, user_id: int = Depends(current_user)
) -> schemas.QueueOut:
    """Новые слова из общего словаря (или из набора deck), сразу карточками."""
    async with request.app.state.pool.acquire() as conn:
        left = NEW_PER_DAY - await repo.new_today(conn, user_id, settings().tz)
        rows = await repo.discover(conn, user_id, min(DISCOVER_LIMIT, left), deck) if left > 0 else []
    out = _cards_out(rows)
    out.new_left = max(0, left - len(rows))
    return out


@router.post("/review", response_model=schemas.ReviewOut)
async def post_review(
    body: schemas.Review, request: Request, user_id: int = Depends(current_user)
) -> schemas.ReviewOut:
    async with request.app.state.pool.acquire() as conn:
        card = await repo.get_card(conn, user_id, body.card_id)
        if card is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "карточка не найдена")
        updated = srs.review(card, body.rating)
        await repo.apply_review(
            conn, user_id, body.card_id, body.rating, body.mode, updated, settings().tz
        )

    return schemas.ReviewOut(
        card_id=body.card_id, due=updated["due"], state=updated["state"]
    )


@router.put("/cards/{card_id}/note", status_code=status.HTTP_204_NO_CONTENT)
async def put_note(
    card_id: int, body: schemas.Note, request: Request, user_id: int = Depends(current_user)
) -> None:
    """Своя ассоциация к слову, которое не держится. Пустая — стереть."""
    async with request.app.state.pool.acquire() as conn:
        if not await repo.set_note(conn, user_id, card_id, body.note.strip() or None):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "карточка не найдена")


@router.put("/cards/{card_id}/known", status_code=status.HTTP_204_NO_CONTENT)
async def mark_known(card_id: int, request: Request, user_id: int = Depends(current_user)) -> None:
    await _set_known(request, user_id, card_id, True)


@router.delete("/cards/{card_id}/known", status_code=status.HTTP_204_NO_CONTENT)
async def unmark_known(card_id: int, request: Request, user_id: int = Depends(current_user)) -> None:
    await _set_known(request, user_id, card_id, False)


async def _set_known(request: Request, user_id: int, card_id: int, known: bool) -> None:
    async with request.app.state.pool.acquire() as conn:
        if not await repo.set_known(conn, user_id, card_id, known):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "карточка не найдена")


@router.get("/quiz", response_model=schemas.QuizOut)
async def get_quiz(
    request: Request,
    mode: Literal["any", "irregular", "cloze", "learn"] = "any",
    limit: int = Query(default=10, ge=1, le=50),
    user_id: int = Depends(current_user),
) -> schemas.QuizOut:
    """Карточки для теста вместе с вариантами ответа. Ответ теста — обычный
    POST /review: оценку ставит не человек, а проверка ответа."""
    fetch = limit * CLOZE_OVERSAMPLE if mode == "cloze" else limit
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.quiz_cards(conn, user_id, mode if mode in repo.QUIZ_FILTERS else "any", fetch)
        pool = await repo.distractors(conn, DISTRACTOR_POOL)
    rng = random.Random()
    cards = []
    for row in quiz.spread(rows):
        gap = quiz.cloze(row["word"], row["forms"], row["examples"])
        if mode == "cloze" and gap is None:
            continue
        cards.append(schemas.QuizCard(
            **dict(row),
            top=lexicon.rank_label(row["zipf"], row["level"]),
            remembered_due=srs.review(row, srs.REMEMBERED)["due"],
            choices_ru=quiz.choices(row, pool, "translation", rng),
            choices_en=quiz.choices(row, pool, "lemma", rng),
            cloze=gap,
        ))
    return schemas.QuizOut(cards=cards[:limit])


@router.post("/reports", status_code=status.HTTP_204_NO_CONTENT)
async def post_report(
    body: schemas.Report, request: Request, user_id: int = Depends(current_user)
) -> None:
    """Жалоба на слово общего словаря: опечатка, перевод, пример."""
    comment = (body.comment or "").strip() or None
    async with request.app.state.pool.acquire() as conn:
        if not await repo.report(conn, user_id, body.word_id, body.reason, comment):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "такого слова в словаре нет")


FEEDBACK_TITLES = {"review": "💬 Отзыв", "idea": "💡 Предложение", "bug": "🐞 Ошибка в приложении",
                   "exercise": "📒 Ошибка в задании"}


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def post_feedback(
    body: schemas.Feedback, request: Request, background: BackgroundTasks,
    who: Identity = Depends(identity), user_id: int = Depends(current_user),
) -> None:
    """Отзыв, идея или ошибка — админам в личку от бота. Сообщение уходит
    сразу, а черновик ответа ИИ пишет следом: ученик его не ждёт."""
    item = None
    if body.item:
        item = grammar.content().items.get(body.item)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"задания {body.item} нет в тетради")
    text = body.text.strip()
    async with request.app.state.pool.acquire() as conn:
        feedback_id = await repo.add_feedback(conn, user_id, body.kind, text, body.item)
    author = escape(who.name or str(who.tg_id))
    lines = [f'{FEEDBACK_TITLES[body.kind]} #{feedback_id} от <a href="tg://user?id={who.tg_id}">{author}</a>']
    if item:
        lines.append(f"Упражнение {item.exercise}, № {item.n}: <i>{escape(grammar.plain(item.text))}</i>")
    lines.append(escape(text))
    sent = await _to_admins(request, {"text": "\n\n".join(lines), "parse_mode": "HTML"})
    if not sent:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Не отправилось, попробуй ещё раз")
    background.add_task(_offer_reply, request, feedback_id, _about(body.kind, text, item), sent)


async def _to_admins(request: Request, message: dict) -> dict[int, int]:
    """Сообщение каждому админу; вернёт, кому дошло: чат → id сообщения."""
    sent = {}
    for chat_id in settings().admins:
        answer = (await request.app.state.telegram.post("/sendMessage", json={"chat_id": chat_id, **message})).json()
        if answer.get("ok"):
            sent[chat_id] = answer["result"]["message_id"]
        else:
            log.warning("отзыв не дошёл до админа %s: %s", chat_id, answer.get("description"))
    return sent


def _about(kind: str, text: str, item: grammar.Item | None) -> str:
    """Что видит ИИ: сообщение и, для задания, предложение с разбором ключа."""
    about = f"Вид: {FEEDBACK_TITLES[kind]}\nСообщение: {text}"
    if item is None:
        return about
    task = grammar.content().exercises[item.exercise]
    return (f"{about}\nЗадание: {task}\nПредложение: {grammar.plain(item.text)}\n"
            f"Перевод: {item.ru}\nРазбор ответа из ключа: {item.why}")


async def _offer_reply(request: Request, feedback_id: int, about: str, sent: dict[int, int]) -> None:
    """Черновик ответа ответом на сообщение админу, с кнопками решения."""
    try:
        draft = await enrich.feedback_reply(settings(), about)
    except enrich.EnrichError:
        draft = None
    if draft:
        async with request.app.state.pool.acquire() as conn:
            await repo.set_feedback_draft(conn, feedback_id, draft)
        text = f"✍️ Черновик ответа:\n\n{draft}"
        buttons = [{"text": "✅ Отправить", "callback_data": f"fb:send:{feedback_id}"},
                   {"text": "✏️ Изменить", "callback_data": f"fb:edit:{feedback_id}"}]
    else:
        text = "ИИ не написал черновик — ответь сам."
        buttons = [{"text": "✏️ Ответить", "callback_data": f"fb:edit:{feedback_id}"}]
    buttons.append({"text": "🚫 Без ответа", "callback_data": f"fb:skip:{feedback_id}"})
    for chat_id, message_id in sent.items():
        answer = (await request.app.state.telegram.post("/sendMessage", json={
            "chat_id": chat_id, "text": text, "reply_parameters": {"message_id": message_id},
            "reply_markup": {"inline_keyboard": [buttons]},
        })).json()
        if not answer.get("ok"):
            log.warning("черновик #%s не дошёл до админа %s: %s", feedback_id, chat_id, answer.get("description"))


@router.post("/admin/feedback/{feedback_id}/answer", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(admin_user)])
async def answer_feedback(feedback_id: int, body: schemas.FeedbackAnswer, request: Request) -> None:
    """Ответ автору от бота: свой текст админа или черновик ИИ как есть."""
    async with request.app.state.pool.acquire() as conn:
        row = await repo.open_feedback(conn, feedback_id)
        if row is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "уже закрыто")
        answer = (body.text or "").strip() or row["draft"]
        if not answer:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "черновика нет — напиши ответ сам")
        quote = row["text"] if len(row["text"]) <= 300 else row["text"][:300] + "…"
        result = (await request.app.state.telegram.post("/sendMessage", json={
            "chat_id": row["tg_id"], "parse_mode": "HTML",
            "text": f"💬 Ответ на твоё сообщение\n<blockquote>{escape(quote)}</blockquote>\n{escape(answer)}",
        })).json()
        if not result.get("ok"):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Telegram не доставил: {result.get('description')}")
        await repo.close_feedback(conn, feedback_id, "answered", answer)


@router.post("/admin/feedback/{feedback_id}/skip", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(admin_user)])
async def skip_feedback(feedback_id: int, request: Request) -> None:
    async with request.app.state.pool.acquire() as conn:
        if await repo.open_feedback(conn, feedback_id) is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "уже закрыто")
        await repo.close_feedback(conn, feedback_id, "skipped", None)


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
async def client_error(body: schemas.ClientError, who: Identity = Depends(identity)) -> None:
    """Падение мини-аппа у пользователя — в лог API. Только от своих
    (initData или токен), чтобы лог не забивали снаружи."""
    log.warning(
        "мини-апп упал у %s (%s): %s\n%s\nUA: %s",
        who.tg_id, body.where, body.message, body.stack, body.ua,
    )


@router.get("/me", response_model=schemas.Me)
async def get_me(
    request: Request, who: Identity = Depends(identity), user_id: int = Depends(current_user)
) -> schemas.Me:
    """Что показывать в меню: «Админка» — админам, «Ученики» — учителям."""
    admin = settings().is_admin(who.tg_id)
    async with request.app.state.pool.acquire() as conn:
        teacher = admin or await repo.is_teacher(conn, user_id)
        grammar = await repo.grammar_summary(conn, user_id)
        in_class = await repo.in_class(conn, user_id)
    return schemas.Me(
        is_admin=admin, is_teacher=teacher, in_class=in_class,
        grammar_done=grammar["done"], grammar_wrong=grammar["wrong_now"],
    )


@router.get("/admin/summary", response_model=schemas.AdminSummary,
            dependencies=[Depends(admin_user)])
async def admin_summary(request: Request) -> schemas.AdminSummary:
    async with request.app.state.pool.acquire() as conn:
        return schemas.AdminSummary(**dict(await repo.admin_summary(conn)))


@router.get("/admin/reports", response_model=list[schemas.ReportedWord],
            dependencies=[Depends(admin_user)])
async def admin_reports(request: Request) -> list[schemas.ReportedWord]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.open_reports(conn)
    return [schemas.ReportedWord(**dict(r)) for r in rows]


@router.post("/admin/reports/{word_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(admin_user)])
async def admin_dismiss(word_id: int, request: Request) -> None:
    """Жалобы не по делу: слово остаётся как есть."""
    async with request.app.state.pool.acquire() as conn:
        await repo.resolve_reports(conn, word_id)


@router.get("/admin/words", response_model=list[schemas.AdminWord],
            dependencies=[Depends(admin_user)])
async def admin_words(
    request: Request, q: str = Query(min_length=1, max_length=100)
) -> list[schemas.AdminWord]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.admin_words(conn, repo.normalize_word(q), 50)
    return [schemas.AdminWord(**dict(r)) for r in rows]


@router.put("/admin/words/{word_id}", response_model=schemas.AdminWord,
            dependencies=[Depends(admin_user)])
async def admin_update_word(
    word_id: int, body: schemas.WordEdit, request: Request
) -> schemas.AdminWord:
    fields = body.model_dump()
    fields["translation"] = fields["translation"].strip()
    async with request.app.state.pool.acquire() as conn:
        row = await repo.update_word(conn, word_id, fields)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "такого слова в словаре нет")
    return schemas.AdminWord(**dict(row))


@router.get("/stats", response_model=schemas.StatsOut)
async def get_stats(
    request: Request, user_id: int = Depends(current_user)
) -> schemas.StatsOut:
    tz = settings().tz
    async with request.app.state.pool.acquire() as conn:
        row = await repo.stats(conn, user_id, tz)
        days = await repo.forecast(conn, user_id, tz, FORECAST_DAYS)
        streak = await repo.streak(conn, user_id, tz)
        decks = await repo.deck_progress(conn, user_id)
        new = await repo.new_today(conn, user_id, tz)

    return schemas.StatsOut(
        **dict(row),
        **dict(streak),
        decks=[schemas.DeckProgress(**dict(d)) for d in decks],
        new_left=max(0, NEW_PER_DAY - new),
        forecast=[schemas.ForecastDay(day=d["day"], count=d["count"]) for d in days],
    )


@router.get("/leaderboard", response_model=schemas.LeaderboardOut)
async def get_leaderboard(
    request: Request,
    scope: Literal["global", "class"] = "global",
    user_id: int = Depends(current_user),
) -> schemas.LeaderboardOut:
    """scope=class — рейтинг среди своих классов: одноклассники и учителя."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.leaderboard(conn, settings().tz, user_id if scope == "class" else None)
    me = next((r for r in rows if r["user_id"] == user_id), None)
    return schemas.LeaderboardOut(
        top=[schemas.LeaderRow(**dict(r)) for r in rows[:LEADERBOARD_SIZE]],
        me=schemas.LeaderRow(**dict(me)) if me else None,
    )


@router.get("/words/search", response_model=list[schemas.SearchHit])
async def search_words(
    request: Request, q: str, limit: int = 20, user_id: int = Depends(current_user)
) -> list[schemas.SearchHit]:
    """Поиск по своим словам. went найдёт go: ищем по лемме запроса."""
    query = repo.normalize_word(q)
    if lexicon.is_word(query):
        query = lexicon.analyze(query).lemma
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.search(conn, user_id, query, min(limit, 100))
    return [schemas.SearchHit(**dict(row)) for row in rows]


@router.get("/words/top", response_model=list[schemas.TopWord])
async def top_words(
    request: Request, limit: int = 20, user_id: int = Depends(current_user)
) -> list[schemas.TopWord]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.top_words(conn, user_id, min(limit, 100))
    return [
        schemas.TopWord(**dict(row), top=lexicon.rank_label(row["zipf"], row["level"]))
        for row in rows
    ]


@router.get("/words/weak", response_model=list[schemas.WeakCard])
async def weak_words(
    request: Request, limit: int = 20, user_id: int = Depends(current_user)
) -> list[schemas.WeakCard]:
    """Карточки, на которых чаще всего сыплемся — вход для упражнений в Claude."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.weak_cards(conn, user_id, min(limit, 100))
    return [schemas.WeakCard(**dict(row)) for row in rows]


def at_local_hours(rows, hours: list[int], now: datetime) -> list[tuple]:
    """Строки с полем tz, у которых местный час сейчас — один из hours, и сам
    этот час. Бот спрашивает раз в час, поэтому каждому час выпадает однажды."""
    local = [(r, now.astimezone(ZoneInfo(r["tz"])).hour) for r in rows]
    return [(r, hour) for r, hour in local if hour in hours]


@router.get(
    "/internal/reminders",
    response_model=list[schemas.ReminderTarget],
    dependencies=[Depends(service_only)],
)
async def internal_reminders(request: Request) -> list[schemas.ReminderTarget]:
    """Кто сегодня ещё не занимался и у кого сейчас час напоминаний. Планировщик
    живёт в процессе бота, а в базу ходит только API — иначе схему знали бы
    два процесса.
    """
    cfg = settings()
    hours = cfg.reminder_hour_list
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.reminder_targets(conn, cfg.tz)
    return [
        schemas.ReminderTarget(**dict(r), evening=hour == max(hours))
        for r, hour in at_local_hours(rows, hours, datetime.now(UTC))
    ]


@router.get("/internal/digest", response_model=list[schemas.Digest], dependencies=[Depends(service_only)])
async def internal_digest(request: Request) -> list[schemas.Digest]:
    """Сводки тетради за неделю, каждому учителю — по его ученикам: бот в базу не ходит."""
    digests = []
    async with request.app.state.pool.acquire() as conn:
        for teacher in await repo.teachers(conn):
            data = await repo.digest(conn, teacher["user_id"])
            digests.append(schemas.Digest(
                students=[dict(r) for r in data["students"]],
                hard_items=[dict(r) for r in data["hard_items"]],
                teachers=[teacher["tg_id"]],
            ))
    return digests


@router.get("/internal/word-of-day", response_model=list[schemas.WordOfDay],
            dependencies=[Depends(service_only)])
async def internal_word_of_day(request: Request) -> list[schemas.WordOfDay]:
    """Слово дня тем, у кого сейчас его час: из случайного решённого задания
    тетради — слово, которого у человека ещё нет в карточках."""
    cfg = settings()
    items = grammar.content().items
    out = []
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.word_of_day_users(conn, cfg.tz)
        for row, _ in at_local_hours(rows, [cfg.word_hour], datetime.now(UTC)):
            done = [items[k] for k in row["items"] if k in items]
            # Несколько попыток: в коротком предложении подходящего слова может не быть.
            for item in random.sample(done, min(5, len(done))):
                word = await repo.word_to_learn(conn, row["user_id"], re.findall(r"[a-z]+", item.en.lower()))
                if word and await _sense_fits(cfg, word, item.en):
                    out.append(schemas.WordOfDay(tg_id=row["tg_id"], lemma=word["lemma"], ipa=word["ipa"],
                                                 translation=word["translation"], exercise=item.exercise,
                                                 en=item.en, ru=item.ru))
                    break
    return out


async def _sense_fits(cfg: Settings, word, sentence: str) -> bool:
    try:
        return await enrich.sense_fits(cfg, word["lemma"], word["translation"], sentence)
    except enrich.EnrichError:
        # ИИ недоступен — слово дня лучше пропустить, чем учить не тому значению.
        return False


@router.post("/me/word-of-day/off", status_code=status.HTTP_204_NO_CONTENT)
async def word_of_day_off(request: Request, who: Identity = Depends(identity)) -> None:
    async with request.app.state.pool.acquire() as conn:
        await repo.stop_word_of_day(conn, who.tg_id)


@router.get(
    "/internal/warmup",
    response_model=list[schemas.WarmupTarget],
    dependencies=[Depends(service_only)],
)
async def internal_warmup(request: Request) -> list[schemas.WarmupTarget]:
    """Кому слать разминку в чат: у кого есть слова к повторению и сейчас час разминки."""
    cfg = settings()
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.warmup_targets(conn, cfg.tz)
    return [
        schemas.WarmupTarget(**dict(r))
        for r, _ in at_local_hours(rows, cfg.warmup_hour_list, datetime.now(UTC))
    ]


@router.get("/games/verbs", response_model=schemas.VerbsOut)
async def get_verbs(request: Request, user_id: int = Depends(current_user)) -> schemas.VerbsOut:
    """Глаголы для игры на скорость в чате и рекорд игрока."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.frequent_verbs(conn, VERBS_GAME)
        best = await repo.verbs_best(conn, user_id)
    return schemas.VerbsOut(verbs=[schemas.Verb(**dict(r)) for r in rows], best=best)


@router.post("/games/verbs", response_model=schemas.Best)
async def post_verbs(
    body: schemas.VerbsScore, request: Request, user_id: int = Depends(current_user)
) -> schemas.Best:
    async with request.app.state.pool.acquire() as conn:
        return schemas.Best(best=await repo.verbs_best(conn, user_id, body.score))


@router.post(
    "/internal/ban",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(service_only)],
)
async def internal_ban(body: schemas.Ban, request: Request) -> None:
    """Убирает слово из общего словаря у всех. Зовёт бот по команде владельца."""
    async with request.app.state.pool.acquire() as conn:
        if not await repo.ban_word(conn, repo.normalize_word(body.word)):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "такого слова в словаре нет")
