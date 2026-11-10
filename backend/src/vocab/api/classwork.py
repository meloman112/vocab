"""Классы и тесты учителя. Ответы проверяет сервер: ключ не уходит ученику
до срока, иначе его было бы видно в мини-аппе."""

import asyncio
import base64
import binascii
import logging
import secrets
from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from .. import classwork, enrich, repo
from ..config import settings
from . import schemas
from .auth import current_user, service_only, teacher_user

router = APIRouter()
log = logging.getLogger(__name__)

CLASS_PREFIX = "class_"

_bot_username: str | None = None


async def _telegram(method: str, **payload: Any) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings().bot_token}/{method}", json=payload
        )
    answer = response.json()
    if not answer.get("ok"):
        raise RuntimeError(f"Telegram {method}: {answer.get('description')}")
    return answer["result"]


async def _class_link(code: str) -> str:
    global _bot_username
    _bot_username = _bot_username or (await _telegram("getMe"))["username"]
    return f"https://t.me/{_bot_username}?start={CLASS_PREFIX}{code}"


def _today():
    return datetime.now(ZoneInfo(settings().tz)).date()


# --- классы ----------------------------------------------------------------------


@router.get("/teacher/classes", response_model=list[schemas.ClassOut])
async def get_classes(request: Request, teacher_id: int = Depends(teacher_user)) -> list[schemas.ClassOut]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.teacher_classes(conn, teacher_id)
    return [schemas.ClassOut(**dict(r), link=await _class_link(r["code"])) for r in rows]


@router.post("/teacher/classes", response_model=schemas.ClassOut)
async def post_class(
    body: schemas.ClassIn, request: Request, teacher_id: int = Depends(teacher_user)
) -> schemas.ClassOut:
    async with request.app.state.pool.acquire() as conn:
        row = await repo.create_class(conn, teacher_id, body.name.strip(), secrets.token_urlsafe(9))
    return schemas.ClassOut(**dict(row), link=await _class_link(row["code"]))


@router.post("/classes/{code}/join", response_model=schemas.Joined)
async def join_class(code: str, request: Request, user_id: int = Depends(current_user)) -> schemas.Joined:
    async with request.app.state.pool.acquire() as conn:
        row = await repo.join_class(conn, code, user_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого класса")
    return schemas.Joined(class_name=row["name"], **{k: row[k] for k in ("teacher", "teacher_tg_id", "joined")})


# --- учитель: тесты --------------------------------------------------------------


@router.post("/teacher/tests/preview", response_model=schemas.TestPreview,
             dependencies=[Depends(teacher_user)])
async def preview_test(body: schemas.TestText) -> schemas.TestPreview:
    """Как сервер поймёт текст учителя: мини-апп показывает это под полем ввода."""
    questions, errors = classwork.parse_text(body.text)
    return schemas.TestPreview(questions=questions, errors=errors)


# ИИ разбирает контрольную дольше минуты, а прокси перед сервером рвёт запрос
# на 60 с, поэтому разбор идёт в фоне, а мини-апп опрашивает результат.
# Процесс API один, так что словаря в памяти хватает.
_jobs: dict[str, asyncio.Task[list[schemas.ConvertedLine]]] = {}


@router.post("/teacher/tests/convert", response_model=schemas.ConvertJob,
             dependencies=[Depends(teacher_user)])
async def convert_test(body: schemas.ConvertIn) -> schemas.ConvertJob:
    """Готовая контрольная учителя (текст или .docx) → строки теста через ИИ."""
    text = body.text.strip()
    if body.docx:
        try:
            text = classwork.docx_text(base64.b64decode(body.docx, validate=True))
        except (binascii.Error, classwork.QuestionError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Это не файл Word (.docx)") from exc
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Пустой текст: вставь контрольную или выбери файл")
    job = secrets.token_urlsafe(16)
    _jobs[job] = asyncio.create_task(_convert(text[:20000]))
    return schemas.ConvertJob(job=job)


@router.get("/teacher/tests/convert/{job}", response_model=list[schemas.ConvertedLine] | None,
            dependencies=[Depends(teacher_user)])
async def convert_result(job: str) -> list[schemas.ConvertedLine] | None:
    """null — ИИ ещё думает."""
    task = _jobs.get(job)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Разбор потерялся, запусти ещё раз")
    if not task.done():
        return None
    del _jobs[job]
    try:
        return task.result()
    except enrich.EnrichError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "ИИ сейчас не отвечает, попробуй чуть позже.") from exc


async def _convert(text: str) -> list[schemas.ConvertedLine]:
    out = []
    for r in await enrich.convert_test(settings(), text):
        try:
            classwork.parse_line(r["line"])
            error = ""
        except classwork.QuestionError as exc:
            error = str(exc)
        out.append(schemas.ConvertedLine(**r, error=error))
    return out


@router.post("/teacher/tests", response_model=schemas.TestCreated)
async def post_test(
    body: schemas.TestIn, request: Request, background: BackgroundTasks,
    teacher_id: int = Depends(teacher_user),
) -> schemas.TestCreated:
    questions, errors = classwork.parse_text(body.text)
    if errors:
        e = errors[0]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Строка {e['line']}: {e['error']}" if e["line"] else e["error"])
    if not questions:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "В тесте нет ни одного вопроса")
    if body.due < _today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Срок уже прошёл")
    async with request.app.state.pool.acquire() as conn:
        if not await repo.owns_class(conn, body.class_id, teacher_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого класса")
        test_id = await repo.create_test(conn, body.class_id, body.title.strip(), questions, body.due)
        tg_ids = await repo.class_member_tg_ids(conn, body.class_id)
        teacher = await repo.student(conn, teacher_id)
    text = (f"📝 Новый тест от {teacher['name']}: «{body.title.strip()}»\n"
            f"Вопросов: {len(questions)} · сдать до {body.due:%d.%m} · одна попытка")
    background.add_task(_announce, tg_ids, text, test_id)
    return schemas.TestCreated(id=test_id, sent=len(tg_ids))


async def _announce(tg_ids: list[int], text: str, test_id: int) -> None:
    for tg_id in tg_ids:
        await _send_test(tg_id, text, test_id)


async def _send_test(tg_id: int, text: str, test_id: int) -> None:
    """Сообщение ученику с кнопкой, открывающей тест. Ученик, заблокировавший
    бота, не должен обрывать рассылку остальным."""
    button = {"text": "Открыть тест", "web_app": {"url": f"{settings().miniapp_url}?screen=test&id={test_id}"}}
    try:
        await _telegram("sendMessage", chat_id=tg_id, text=text,
                        reply_markup={"inline_keyboard": [[button]]})
    except Exception as exc:  # noqa: BLE001
        log.warning("не отправил тест %s ученику %s: %s", test_id, tg_id, exc)


@router.get("/teacher/tests", response_model=list[schemas.TestRow])
async def get_tests(request: Request, teacher_id: int = Depends(teacher_user)) -> list[schemas.TestRow]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.teacher_tests(conn, teacher_id, settings().tz)
    return [schemas.TestRow(**dict(r)) for r in rows]


@router.get("/teacher/tests/{test_id}", response_model=schemas.TestReport)
async def get_test_report(
    test_id: int, request: Request, teacher_id: int = Depends(teacher_user)
) -> schemas.TestReport:
    async with request.app.state.pool.acquire() as conn:
        test = await repo.teacher_test(conn, test_id, teacher_id, settings().tz)
        if test is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого теста")
        rows = await repo.test_results(conn, test_id)
        accepted = await repo.test_accepted(conn, test_id)
    return _report(test, rows, accepted)


def _report(test, rows, accepted: dict[int, set[str]]) -> schemas.TestReport:
    questions = test["questions"]
    owner = [qi for qi, q in enumerate(questions) for p in q["parts"] if isinstance(p, dict)]
    correct = [0] * len(owner)
    wrong: list[Counter] = [Counter() for _ in owner]
    students = []
    for r in rows:
        marks = classwork.marks(questions, r["answers"], accepted) if r["answers"] is not None else None
        for i, ok in enumerate(marks or []):
            if ok:
                correct[i] += 1
            else:
                wrong[i][r["answers"][i].strip().lower() if i < len(r["answers"]) else ""] += 1
        students.append(schemas.StudentScore(
            user_id=r["user_id"], name=r["name"], submitted_at=r["submitted_at"],
            score=sum(marks) if marks is not None else None, answers=r["answers"], marks=marks,
        ))
    gaps = [
        schemas.GapStat(gap=i, question=owner[i], correct=correct[i],
                        wrong=[schemas.WrongAnswer(answer=a, count=n) for a, n in wrong[i].most_common()])
        for i in range(len(owner))
    ]
    return schemas.TestReport(
        **{k: test[k] for k in ("id", "title", "due", "class_name", "closed")},
        questions=questions, gaps=gaps, students=students,
    )


@router.post("/teacher/tests/{test_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_answer(
    test_id: int, body: schemas.AcceptIn, request: Request, teacher_id: int = Depends(teacher_user)
) -> None:
    """Ответ верный, а ключ его не знал: засчитывается у всех, кто так ответил."""
    async with request.app.state.pool.acquire() as conn:
        test = await repo.teacher_test(conn, test_id, teacher_id, settings().tz)
        if test is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого теста")
        if body.gap >= len(classwork.gaps(test["questions"])):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "нет такого пропуска")
        await repo.accept_test_answer(conn, test_id, body.gap, classwork.norm(body.answer))


@router.delete("/teacher/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(test_id: int, request: Request, teacher_id: int = Depends(teacher_user)) -> None:
    async with request.app.state.pool.acquire() as conn:
        if not await repo.delete_test(conn, test_id, teacher_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "нет такого теста")


# --- ученик ----------------------------------------------------------------------


def _student_view(row, accepted: dict[int, set[str]]) -> schemas.StudentTest:
    """До срока ученик видит вопросы без ответов и свои ответы; после срока —
    ключ, отметки и балл."""
    questions = row["questions"]
    show = row["closed"] and row["answers"] is not None
    marks = classwork.marks(questions, row["answers"], accepted) if show else None
    return schemas.StudentTest(
        **{k: row[k] for k in ("id", "title", "due", "teacher", "closed", "submitted_at", "answers")},
        total=len(classwork.gaps(questions)),
        score=sum(marks) if marks is not None else None,
        questions=questions if row["closed"] else classwork.hide_answers(questions),
        marks=marks,
    )


@router.get("/tests", response_model=list[schemas.StudentTest])
async def get_my_tests(request: Request, user_id: int = Depends(current_user)) -> list[schemas.StudentTest]:
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.student_tests(conn, user_id, settings().tz)
        return [_student_view(r, await repo.test_accepted(conn, r["id"])) for r in rows]


@router.get("/tests/{test_id}", response_model=schemas.StudentTest)
async def get_my_test(test_id: int, request: Request, user_id: int = Depends(current_user)) -> schemas.StudentTest:
    async with request.app.state.pool.acquire() as conn:
        row = await repo.student_test(conn, test_id, user_id, settings().tz)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этого теста нет в твоих классах")
        return _student_view(row, await repo.test_accepted(conn, test_id))


@router.post("/tests/{test_id}/submit", status_code=status.HTTP_204_NO_CONTENT)
async def submit_test(
    test_id: int, body: schemas.SubmitIn, request: Request, user_id: int = Depends(current_user)
) -> None:
    async with request.app.state.pool.acquire() as conn:
        row = await repo.student_test(conn, test_id, user_id, settings().tz)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этого теста нет в твоих классах")
        if row["closed"]:
            raise HTTPException(status.HTTP_410_GONE, "Срок сдачи прошёл")
        if len(body.answers) != len(classwork.gaps(row["questions"])):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ответы не совпадают с вопросами")
        if not await repo.submit_test(conn, test_id, user_id, [a.strip() for a in body.answers]):
            raise HTTPException(status.HTTP_409_CONFLICT, "Тест уже сдан")


@router.get("/internal/test-reminders", response_model=list[schemas.TestReminder],
            dependencies=[Depends(service_only)])
async def test_reminders(request: Request) -> list[schemas.TestReminder]:
    """Кто не сдал тест со сроком завтра — бот напомнит."""
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.test_reminders(conn, settings().tz)
    return [schemas.TestReminder(**dict(r)) for r in rows]
