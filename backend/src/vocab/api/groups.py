"""Класс в Telegram-группе. Бот присылает chat_id, всё остальное решает API:
кто учитель, кто помощник и какая домашка."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import grammar, repo
from . import schemas
from .auth import current_user, teacher_user

router = APIRouter(prefix="/groups/{chat_id}")

# Бот отличает «чат не привязан» от «домашки нет» по тексту: оба ответа 404.
UNBOUND = "группа не привязана к классу"
NO_HOMEWORK = "домашки нет"


async def _chat_class(conn, chat_id: int, user_id: int):
    cls = await repo.chat_class(conn, chat_id, user_id)
    if cls is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNBOUND)
    return cls


def _require_helper(cls, user_id: int) -> None:
    if user_id != cls["teacher_id"] and not cls["assistant"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "только учитель или помощник")


def _item_count(exercises: list[int]) -> int:
    chosen = set(exercises)
    return sum(1 for i in grammar.content().items.values() if i.exercise in chosen)


@router.post("/bind")
async def bind(
    chat_id: int, body: schemas.BindIn, request: Request, teacher_id: int = Depends(current_user)
) -> dict:
    """Несколько классов и class_id не указан — привязки нет, в ответе список на выбор.
    Классов нет — создаётся новый, и привязавший становится учителем."""
    async with request.app.state.pool.acquire() as conn:
        # Привязать может любой, поэтому чужую группу отнять нельзя.
        bound = await repo.chat_class(conn, chat_id, teacher_id)
        if bound is not None and bound["teacher_id"] != teacher_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "группа привязана к классу другого учителя")
        classes = await repo.teacher_classes(conn, teacher_id)
        if body.class_id is not None:
            chosen = next((c for c in classes if c["id"] == body.class_id), None)
        elif len(classes) > 1:
            return {"bound": None, "classes": [{"id": c["id"], "name": c["name"]} for c in classes]}
        elif classes:
            chosen = classes[0]
        else:
            chosen = await repo.create_class(conn, teacher_id, body.title.strip(), secrets.token_urlsafe(9))
        if chosen is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого класса")
        await repo.bind_chat(conn, chosen["id"], chat_id)
    return {"bound": chosen["name"], "classes": []}


@router.post("/join")
async def join(chat_id: int, request: Request, user_id: int = Depends(current_user)) -> dict:
    async with request.app.state.pool.acquire() as conn:
        cls = await _chat_class(conn, chat_id, user_id)
        joined = await repo.join_chat_class(conn, cls["id"], user_id)
    return {"class_name": cls["name"], "joined": joined}


@router.post("/assistant")
async def assistant(
    chat_id: int, body: schemas.AssistantIn, request: Request, teacher_id: int = Depends(teacher_user)
) -> dict:
    async with request.app.state.pool.acquire() as conn:
        cls = await _chat_class(conn, chat_id, teacher_id)
        if cls["teacher_id"] != teacher_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "это не твой класс")
        user_id = await repo.ensure_user(conn, body.tg_id, body.name or None)
        enabled = await repo.toggle_assistant(conn, cls["id"], user_id)
    return {"name": body.name, "assistant": enabled}


@router.put("/homework")
async def put_homework(
    chat_id: int, body: schemas.HomeworkIn, request: Request, user_id: int = Depends(current_user)
) -> dict:
    exercises = sorted(set(body.exercises))
    async with request.app.state.pool.acquire() as conn:
        cls = await _chat_class(conn, chat_id, user_id)
        _require_helper(cls, user_id)
        missing = [n for n in exercises if n not in grammar.content().exercises]
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Нет упражнений: " + ", ".join(map(str, missing)),
            )
        await repo.set_homework(conn, cls["id"], exercises, user_id)
    return {"exercises": exercises, "items": _item_count(exercises)}


@router.get("/homework")
async def get_homework(chat_id: int, request: Request, user_id: int = Depends(current_user)) -> dict:
    async with request.app.state.pool.acquire() as conn:
        cls = await _chat_class(conn, chat_id, user_id)
        exercises = await repo.homework(conn, cls["id"])
    if exercises is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_HOMEWORK)
    return {"exercises": exercises, "items": _item_count(exercises)}


@router.get("/report")
async def report(chat_id: int, request: Request, user_id: int = Depends(current_user)) -> dict:
    async with request.app.state.pool.acquire() as conn:
        cls = await _chat_class(conn, chat_id, user_id)
        _require_helper(cls, user_id)
        exercises = await repo.homework(conn, cls["id"])
        if exercises is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NO_HOMEWORK)
        rows = await repo.homework_report(conn, cls["id"], exercises)
    return {"exercises": exercises, "total": _item_count(exercises), **rows}
