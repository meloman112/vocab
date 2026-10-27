"""Ручки. Транспортный слой: разбор запроса, вызов repo, сборка DTO."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import dictionary, enrich, lexicon, repo, srs
from ..config import settings
from . import schemas
from .auth import current_user, service_only

router = APIRouter()

FORECAST_DAYS = 7
# Сколько новых слов из общего словаря выдаётся за одно «Давай».
DISCOVER_LIMIT = 10
LEADERBOARD_SIZE = 10


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
            request.app.state.pool, settings(), user_id, body.word
        )
    except dictionary.Rejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except enrich.EnrichError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "ИИ сейчас не отвечает, пришли слово чуть позже."
        ) from exc
    return schemas.AddWordOut(entries=[schemas.WordEntry(**e) for e in entries])


def _cards_out(rows) -> schemas.QueueOut:
    return schemas.QueueOut(cards=[
        schemas.CardOut(**dict(row), top=lexicon.rank_label(row["zipf"]))
        for row in rows
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
    request: Request, user_id: int = Depends(current_user)
) -> schemas.QueueOut:
    """Свои слова кончились — новые из общего словаря, сразу карточками."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.discover(conn, user_id, DISCOVER_LIMIT)
    return _cards_out(rows)


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
            conn, user_id, body.card_id, body.rating, updated, settings().tz
        )

    return schemas.ReviewOut(
        card_id=body.card_id, due=updated["due"], state=updated["state"]
    )


@router.get("/stats", response_model=schemas.StatsOut)
async def get_stats(
    request: Request, user_id: int = Depends(current_user)
) -> schemas.StatsOut:
    tz = settings().tz
    async with request.app.state.pool.acquire() as conn:
        row = await repo.stats(conn, user_id, tz)
        days = await repo.forecast(conn, user_id, tz, FORECAST_DAYS)
        streak = await repo.streak(conn, user_id, tz)

    return schemas.StatsOut(
        **dict(row),
        **dict(streak),
        forecast=[schemas.ForecastDay(day=d["day"], count=d["count"]) for d in days],
    )


@router.get("/leaderboard", response_model=schemas.LeaderboardOut)
async def get_leaderboard(
    request: Request, user_id: int = Depends(current_user)
) -> schemas.LeaderboardOut:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.leaderboard(conn, settings().tz)
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
        schemas.TopWord(**dict(row), top=lexicon.rank_label(row["zipf"]))
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


@router.get(
    "/internal/reminders",
    response_model=list[schemas.ReminderTarget],
    dependencies=[Depends(service_only)],
)
async def internal_reminders(request: Request) -> list[schemas.ReminderTarget]:
    """Кто сегодня ещё не занимался. Планировщик живёт в процессе бота, а в
    базу ходит только API — иначе схему знали бы два процесса.
    """
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.reminder_targets(conn, settings().tz)
    return [schemas.ReminderTarget(**dict(r)) for r in rows]


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
