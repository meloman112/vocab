"""Ручки. Транспортный слой: разбор запроса, вызов repo, сборка DTO."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from .. import enrich, repo, srs
from ..config import settings
from . import schemas
from .auth import current_user, service_only

router = APIRouter()

FORECAST_DAYS = 7
FAILED_LIMIT = 20


@router.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    # Проверка живого соединения с базой, а не только процесса: контейнер,
    # который отвечает 200 без базы, compose считает здоровым напрасно.
    async with request.app.state.pool.acquire() as conn:
        await conn.execute("select 1")
    return {"status": "ok"}


@router.post("/words", response_model=schemas.AddWordOut)
async def add_word(
    body: schemas.AddWord,
    background: BackgroundTasks,
    request: Request,
    user_id: int = Depends(current_user),
) -> schemas.AddWordOut:
    """Создаёт карточку и запускает обогащение в фоне.

    Ответ не ждёт модель: смысл всей затеи — слово попадает в систему
    за две секунды, а перевод догоняет.
    """
    word = repo.normalize_word(body.word)
    if not word:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "пустое слово")

    pool = request.app.state.pool
    async with pool.acquire() as conn:
        card, created = await repo.add_card(conn, user_id, word, body.source_url)

    if created:
        background.add_task(
            enrich.enrich_card, pool, settings(), card["id"], word, body.source_url
        )

    return schemas.AddWordOut(
        id=card["id"], word=card["word"], status=card["status"], created=created
    )


@router.post("/words/{card_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_word(
    card_id: int,
    background: BackgroundTasks,
    request: Request,
    user_id: int = Depends(current_user),
) -> dict[str, str]:
    """Повторное обогащение карточки, у которой не разобрался ответ модели."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        card = await repo.get_card(conn, user_id, card_id)
        if card is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "карточка не найдена")
        await repo.mark_pending(conn, user_id, card_id)

    background.add_task(
        enrich.enrich_card, pool, settings(), card_id, card["word"], card["source_url"]
    )
    return {"status": "pending"}


@router.get("/queue", response_model=schemas.QueueOut)
async def get_queue(
    request: Request, user_id: int = Depends(current_user)
) -> schemas.QueueOut:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.queue(conn, user_id, settings().queue_limit)
    return schemas.QueueOut(cards=[schemas.CardOut(**dict(row)) for row in rows])


@router.post("/review", response_model=schemas.ReviewOut)
async def post_review(
    body: schemas.Review, request: Request, user_id: int = Depends(current_user)
) -> schemas.ReviewOut:
    async with request.app.state.pool.acquire() as conn:
        card = await repo.get_card(conn, user_id, body.card_id)
        if card is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "карточка не найдена")
        updated = srs.review(card, body.rating)
        await repo.apply_review(conn, body.card_id, body.rating, updated)

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

    return schemas.StatsOut(
        **dict(row),
        forecast=[schemas.ForecastDay(day=d["day"], count=d["count"]) for d in days],
    )


@router.get("/words/failed", response_model=list[schemas.FailedCard])
async def get_failed(
    request: Request, user_id: int = Depends(current_user)
) -> list[schemas.FailedCard]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.failed_cards(conn, user_id, FAILED_LIMIT)
    return [schemas.FailedCard(**dict(row)) for row in rows]


@router.get("/words/search", response_model=list[schemas.SearchHit])
async def search_words(
    request: Request, q: str, limit: int = 20, user_id: int = Depends(current_user)
) -> list[schemas.SearchHit]:
    """Нужна MCP-тулу search_words; в ТЗ §6 ручки нет, в §9 тул есть."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.search(conn, user_id, q, min(limit, 100))
    return [schemas.SearchHit(**dict(row)) for row in rows]


@router.get("/words/weak", response_model=list[schemas.WeakCard])
async def weak_words(
    request: Request, limit: int = 20, user_id: int = Depends(current_user)
) -> list[schemas.WeakCard]:
    """Карточки, на которых чаще всего сыплемся — вход для упражнений в Claude."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.weak_cards(conn, user_id, min(limit, 100))
    return [schemas.WeakCard(**dict(row)) for row in rows]


@router.delete("/words/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(
    card_id: int, request: Request, user_id: int = Depends(current_user)
) -> None:
    async with request.app.state.pool.acquire() as conn:
        if not await repo.delete_card(conn, user_id, card_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "карточка не найдена")


@router.get(
    "/internal/due",
    response_model=list[schemas.DueUser],
    dependencies=[Depends(service_only)],
)
async def internal_due(request: Request) -> list[schemas.DueUser]:
    """Кого будить напоминанием. Ручка вне ТЗ: планировщик живёт в процессе
    бота, а в базу ходит только API — иначе схему знали бы два процесса.
    """
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.due_by_user(conn)
    return [schemas.DueUser(tg_id=r["tg_id"], due=r["due"]) for r in rows]
