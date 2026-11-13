"""Ручки тетради и учителя. Ответ ученика проверяет мини-апп: движок с
ключами живёт там, сюда приходит уже итог задания и его ошибки."""

import secrets
import time
from collections import defaultdict

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from .. import enrich, grammar, repo
from ..config import settings
from ..grammar import pdf
from . import schemas
from .auth import Identity, admin_user, current_user, identity, teacher_user

router = APIRouter()

# Ссылка учителя живёт неделю: передают её не сразу, но вечной ей быть незачем.
INVITE_TTL_DAYS = 7
COMMON_MISTAKES = 30
DRILL_VERBS = 40


def _known(item: str) -> grammar.Item:
    found = grammar.content().items.get(item)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"задания {item} нет в тетради")
    return found


@router.get("/grammar/content")
async def get_content(
    _: Identity = Depends(identity),
    if_none_match: str | None = Header(default=None),
) -> Response:
    """Задания отдаются только из Telegram: это книга учителя, в статику она не кладётся."""
    content = grammar.content()
    headers = {"ETag": content.etag, "Cache-Control": "private, no-cache"}
    if if_none_match == content.etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content.raw, media_type="application/json", headers=headers)


@router.get("/grammar/progress", response_model=schemas.GrammarProgress)
async def get_progress(
    request: Request, user_id: int = Depends(current_user)
) -> schemas.GrammarProgress:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.grammar_results(conn, user_id)
        accepted_rows = await repo.grammar_accepted(conn)
    accepted: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in accepted_rows:
        accepted[r["item"]][r["slot"]].append(r["answer"])
    return schemas.GrammarProgress(
        results={
            r["item"]: schemas.GrammarResult(clean=r["clean"], was_wrong=r["was_wrong"],
                                             answers=[a or "" for a in r["answers"]])
            for r in rows
        },
        accepted=accepted,
    )


@router.get("/grammar/verbs", response_model=list[schemas.DrillVerb])
async def get_drill_verbs(
    request: Request, user_id: int = Depends(current_user)
) -> list[schemas.DrillVerb]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.drill_verbs(conn, user_id, DRILL_VERBS)
    return [schemas.DrillVerb(**dict(r)) for r in rows]


@router.post("/grammar/attempts", status_code=status.HTTP_204_NO_CONTENT)
async def post_attempt(
    body: schemas.GrammarAttempt, request: Request, user_id: int = Depends(current_user)
) -> None:
    item = _known(body.item)
    if len(body.answers) != item.slots or any(m.slot >= item.slots for m in body.mistakes):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "пропуски не совпадают с заданием")
    async with request.app.state.pool.acquire() as conn:
        await repo.save_grammar_attempt(
            conn, user_id, body.item, body.clean, [a.strip() for a in body.answers],
            [(m.slot, m.answer.strip(), m.why) for m in body.mistakes], settings().tz,
        )


@router.post("/grammar/recheck", response_model=schemas.RecheckOut)
async def recheck(
    body: schemas.Recheck, request: Request, _: int = Depends(current_user)
) -> schemas.RecheckOut:
    """Ученик считает, что движок зря не принял ответ. Если ИИ согласен,
    ответ засчитывается всем — как ответ, принятый учителем."""
    item = _known(body.item)
    if body.slot >= item.slots:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "нет такого пропуска")
    answer = " ".join(body.answer.split())
    sentence = grammar.plain(item.text)
    if item.slots > 1:
        sentence += f" (проверяем пропуск №{body.slot + 1})"
    try:
        verdict = await enrich.recheck(settings(), grammar.content().exercises[item.exercise],
                                       sentence, body.key, answer)
    except enrich.EnrichError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "ИИ не ответил, попробуй ещё раз") from exc
    if verdict["ok"]:
        async with request.app.state.pool.acquire() as conn:
            await repo.accept_answer(conn, body.item, body.slot, answer)
    return schemas.RecheckOut(**verdict)


@router.post("/grammar/import", response_model=schemas.ImportOut)
async def import_progress(
    body: schemas.GrammarImport, request: Request, user_id: int = Depends(current_user)
) -> schemas.ImportOut:
    """Прогресс прежней тетради из Telegram CloudStorage. Мини-апп шлёт его
    один раз; повтор безопасен — решённое в базе не перетирается."""
    items = grammar.content().items
    rows = [
        (key, r.clean, r.wasWrong or not r.clean, [a or "" for a in r.answers])
        for key, r in body.items.items()
        if key in items
    ]
    async with request.app.state.pool.acquire() as conn:
        return schemas.ImportOut(imported=await repo.import_grammar(conn, user_id, rows))


@router.post("/grammar/pdf", status_code=status.HTTP_204_NO_CONTENT)
async def send_pdf(body: schemas.PdfRequest, who: Identity = Depends(identity)) -> None:
    """Файл собирает и шлёт сервер: токен бота в браузер не попадает,
    а кому слать, известно из подписанного initData."""
    exercises = body.model_dump()["exercises"]
    document = await run_in_threadpool(pdf.render, who.name or "", exercises)
    numbers = ", ".join(str(ex["id"]) for ex in exercises)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings().bot_token}/sendDocument",
            data={"chat_id": who.tg_id, "caption": f"Упражнения {numbers}"},
            files={"document": (f"workbook-{time.strftime('%Y-%m-%d')}.pdf", document, "application/pdf")},
        )
    answer = response.json()
    if not answer.get("ok"):
        # Чаще всего ученик не нажал Start: Telegram не даёт боту писать первым.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Telegram не принял файл: {answer.get('description')}")


# --- учитель -------------------------------------------------------------------


@router.get("/teacher/students", response_model=list[schemas.Student],
            dependencies=[Depends(teacher_user)])
async def get_students(request: Request) -> list[schemas.Student]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.students(conn)
    return [schemas.Student(**dict(r)) for r in rows]


@router.get("/teacher/students/{user_id}", response_model=schemas.StudentDetail,
            dependencies=[Depends(teacher_user)])
async def get_student(user_id: int, request: Request) -> schemas.StudentDetail:
    async with request.app.state.pool.acquire() as conn:
        who = await repo.student(conn, user_id)
        if who is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого ученика")
        results = await repo.student_results(conn, user_id)
        mistakes = await repo.student_mistakes(conn, user_id)
    return schemas.StudentDetail(
        **dict(who),
        results=[schemas.StudentResult(**dict(r)) for r in results],
        mistakes=[schemas.StudentMistake(**dict(m)) for m in mistakes],
    )


@router.post("/teacher/mistakes/{mistake_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_mistake(
    mistake_id: int, request: Request, teacher_id: int = Depends(teacher_user)
) -> None:
    async with request.app.state.pool.acquire() as conn:
        if await repo.accept_mistake(conn, mistake_id, teacher_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такой ошибки")


@router.get("/teacher/mistakes/common", response_model=list[schemas.CommonMistake],
            dependencies=[Depends(teacher_user)])
async def get_common_mistakes(request: Request) -> list[schemas.CommonMistake]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.common_mistakes(conn, COMMON_MISTAKES)
    return [schemas.CommonMistake(**dict(r)) for r in rows]


# --- назначение учителей -------------------------------------------------------


@router.post("/admin/teacher-invites", response_model=schemas.Invite)
async def create_invite(request: Request, admin_id: int = Depends(admin_user)) -> schemas.Invite:
    code = secrets.token_urlsafe(12)
    async with request.app.state.pool.acquire() as conn:
        await repo.create_teacher_invite(conn, admin_id, code)
    return schemas.Invite(code=code, ttl_days=INVITE_TTL_DAYS)


@router.post("/teacher-invites/{code}/redeem", response_model=schemas.Redeemed)
async def redeem_invite(
    code: str, request: Request, user_id: int = Depends(current_user)
) -> schemas.Redeemed:
    async with request.app.state.pool.acquire() as conn:
        row = await repo.redeem_teacher_invite(conn, code, user_id, INVITE_TTL_DAYS)
    if row is None:
        raise HTTPException(status.HTTP_410_GONE, "ссылка уже использована или устарела")
    return schemas.Redeemed(inviter_tg_id=row["inviter_tg_id"])


@router.get("/admin/teachers", response_model=list[schemas.Teacher],
            dependencies=[Depends(admin_user)])
async def get_teachers(request: Request) -> list[schemas.Teacher]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.teachers(conn)
    return [schemas.Teacher(**dict(r)) for r in rows]


@router.delete("/admin/teachers/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(admin_user)])
async def remove_teacher(user_id: int, request: Request) -> None:
    async with request.app.state.pool.acquire() as conn:
        if not await repo.remove_teacher(conn, user_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "такого учителя нет")
