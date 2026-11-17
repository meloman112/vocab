"""Ручки тетради и учителя. Ответ ученика проверяет мини-апп: движок с
ключами живёт там, сюда приходит уже итог задания и его ошибки."""

import logging
import time
from collections import defaultdict

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from .. import enrich, grammar, repo
from ..config import settings
from ..grammar import pdf
from . import schemas
from .auth import Identity, Teacher, admin_user, current_user, identity, teacher

router = APIRouter()
log = logging.getLogger(__name__)

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
        accepted_rows = await repo.grammar_accepted(conn, user_id)
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
    body: schemas.Recheck, request: Request,
    who: Identity = Depends(identity), user_id: int = Depends(current_user),
) -> schemas.RecheckOut:
    """Ученик считает, что движок зря не принял ответ. Если ИИ согласен,
    ответ засчитывается ему и его классам, а всем — только по запросу админа:
    бот открыт, и уговорить модель мог бы кто угодно."""
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
            scope = None if settings().is_admin(who.tg_id) else user_id
            await repo.accept_answer(conn, body.item, body.slot, answer, scope)
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
async def send_pdf(
    body: schemas.PdfRequest, request: Request,
    who: Identity = Depends(identity), user_id: int = Depends(current_user),
) -> None:
    """Файл собирает и шлёт сервер: токен бота в браузер не попадает,
    а кому слать, известно из подписанного initData."""
    t0 = time.perf_counter()
    exercises = body.model_dump()["exercises"]
    keys = [pdf.item_key(ex["id"], i["n"]) for ex in exercises for i in ex["items"] if i["done"]]
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.first_wrong_attempts(conn, user_id, keys)
    wrong = {(r["item"], r["slot"]): (r["answer"], r["why"]) for r in rows}
    summary = pdf.annotate(exercises, wrong)
    t1 = time.perf_counter()
    document = await run_in_threadpool(pdf.render, who.name or "", exercises, summary)
    t2 = time.perf_counter()
    numbers = ", ".join(str(ex["id"]) for ex in exercises)
    try:
        # 60 с, а не общие 30: 17.11 Telegram дважды подряд отвечал на sendDocument дольше 30 с.
        response = await request.app.state.telegram.post(
            "/sendDocument",
            data={"chat_id": who.tg_id, "caption": f"Упражнения {numbers}"},
            files={"document": (f"workbook-{time.strftime('%Y-%m-%d')}.pdf", document, "application/pdf")},
            timeout=60,
        )
    except httpx.TimeoutException as exc:
        # Файл мог и дойти: Telegram принял его, но не успел ответить.
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT,
                            "Telegram долго не отвечает. Проверь чат с ботом, если файла нет — отправь ещё раз") from exc
    t3 = time.perf_counter()
    # Где уходит время, видно в логе: db+annotate / сборка / Telegram.
    log.info("pdf %d упр., %d КБ: db %.0f мс, render %.0f мс, telegram %.0f мс",
             len(exercises), len(document) // 1024, (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000)
    answer = response.json()
    if not answer.get("ok"):
        # Чаще всего ученик не нажал Start: Telegram не даёт боту писать первым.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Telegram не принял файл: {answer.get('description')}")


# --- учитель -------------------------------------------------------------------


@router.get("/teacher/students", response_model=list[schemas.Student])
async def get_students(request: Request, who: Teacher = Depends(teacher)) -> list[schemas.Student]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.students(conn, who.scope)
    return [schemas.Student(**dict(r)) for r in rows]


@router.get("/teacher/students/{user_id}", response_model=schemas.StudentDetail)
async def get_student(
    user_id: int, request: Request, viewer: Teacher = Depends(teacher)
) -> schemas.StudentDetail:
    async with request.app.state.pool.acquire() as conn:
        who = await repo.student(conn, user_id)
        # Чужой ученик неотличим от несуществующего: по id их не перебрать.
        if who is None or not await repo.teaches(conn, viewer.scope, user_id):
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
    mistake_id: int, request: Request, who: Teacher = Depends(teacher)
) -> None:
    async with request.app.state.pool.acquire() as conn:
        if await repo.accept_mistake(conn, mistake_id, who.user_id, who.scope) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такой ошибки")


@router.get("/teacher/mistakes/common", response_model=list[schemas.CommonMistake])
async def get_common_mistakes(
    request: Request, who: Teacher = Depends(teacher)
) -> list[schemas.CommonMistake]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.common_mistakes(conn, COMMON_MISTAKES, who.scope)
    return [schemas.CommonMistake(**dict(r)) for r in rows]


# --- учителя для админа --------------------------------------------------------


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
