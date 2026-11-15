"""Контрольная на уроке. Учитель отдаёт тест боту в личке, а всё остальное
бот делает в группе класса: объявление, кнопка «Закончить», итоги."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import classwork
from ..client import VocabAPI
from ..config import Settings

log = logging.getLogger(__name__)
router = Router()

MESSAGE_LIMIT = 4000
POLL_SECONDS = 3
MINUTES = (15, 20, 30)

# Присланная контрольная ждёт, пока учитель выберет класс и время. Процесс бота один;
# после перезапуска учитель пришлёт текст заново — черновик в базе не нужен.
pending: dict[int, tuple[str, str]] = {}


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    return [*chunks, current] if current else chunks


def render_test(entries: list[tuple[str, str]]) -> tuple[str, list[str], list[int]]:
    """Строки с ошибкой пропускаются. Возвращает текст для запуска, его показ
    по сообщениям (номера — как в исходном списке) и номера пропущенных строк."""
    good = [(n, line) for n, (line, error) in enumerate(entries, 1) if not error]
    skipped = [n for n, (_, error) in enumerate(entries, 1) if error]
    shown = split_message("\n".join(f"{n}. {line}" for n, line in good))
    return "\n".join(line for _, line in good), shown, skipped


def exam_keyboard(classes: list[dict[str, Any]]) -> InlineKeyboardMarkup | None:
    bound = [c for c in classes if c["chat_id"]]
    if not bound:
        return None
    # Название класса нужно, только когда выбирать есть из чего.
    rows = [
        [
            InlineKeyboardButton(
                text=f"{c['name'] + ' ' if len(bound) > 1 else ''}▶️ {m} мин",
                callback_data=f"exam:{c['id']}:{m}",
            )
            for m in MINUTES
        ]
        for c in bound
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def summary_text(summary: dict[str, Any]) -> str:
    students = summary["students"]
    done = sorted((s for s in students if s["score"] is not None), key=lambda s: -s["score"])
    missed = [s for s in students if s["score"] is None]
    lines = [f"⏰ Контрольная «{summary['title']}» закончена", ""]
    lines += [f"• {s['name']} — {s['score']} из {summary['total']}" for s in done]
    lines += [f"• {s['name']} — не сдал" for s in missed]
    if summary["hard"]:
        hard = ", ".join(f"№{h['question']} (верно {h['correct']} из {h['answered']})" for h in summary["hard"])
        lines += ["", f"Труднее всего: {hard}"]
    return "\n".join(lines)


async def _teacher_classes(message: Message, api: VocabAPI) -> list[dict[str, Any]] | None:
    try:
        return await api.teacher_classes(message.from_user.id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 403:
            raise
        await message.answer("Контрольную запускает учитель.")
        return None


async def _wait_conversion(api: VocabAPI, tg_id: int, job: str) -> list[dict[str, Any]]:
    # Конец гарантирует API: разбор либо готов, либо упал с ошибкой ИИ.
    while True:
        await asyncio.sleep(POLL_SECONDS)
        lines = await api.convert_result(tg_id, job)
        if lines is not None:
            return lines


async def _entries(message: Message, api: VocabAPI, text: str) -> list[tuple[str, str]] | None:
    """(строка, ошибка) по каждой строке теста. ИИ зовём, только если текст не в формате."""
    questions, errors = classwork.parse_text(text)
    if questions and not errors:
        return [(classwork.NUMBER.sub("", raw).strip(), "") for raw in text.splitlines() if raw.strip()]
    await message.answer("Разбираю контрольную, это до двух минут…")
    tg_id = message.from_user.id
    try:
        job = await api.convert_test(tg_id, text[:20000])
        lines = await _wait_conversion(api, tg_id, job["job"])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (404, 422, 502):
            raise
        await message.answer(exc.response.json()["detail"])
        return None
    return [(r["line"], r["error"]) for r in lines]


async def _offer(message: Message, api: VocabAPI, classes: list[dict[str, Any]], text: str, title: str) -> None:
    entries = await _entries(message, api, text)
    if entries is None:
        return
    ready, shown, skipped = render_test(entries)
    if not shown:
        await message.answer("Не нашёл ни одного вопроса. Ответ пишется в квадратных скобках: She [doesn't like] coffee.")
        return
    for chunk in shown:
        await message.answer(chunk)
    keyboard = exam_keyboard(classes)
    if keyboard is None:
        await message.answer("Сначала привяжи группу: напиши /bind в группе класса.")
        return
    pending[message.from_user.id] = (title, ready)
    note = f"\nНе вышло превратить в вопрос, эти строки пропущу: {', '.join(map(str, skipped))}." if skipped else ""
    await message.answer(
        f"Вопросов: {len(ready.splitlines())}. Проверь ответы в квадратных скобках. "
        f"Что-то не так: поправь текст и пришли его с командой /test.{note}",
        reply_markup=keyboard,
    )


@router.message(Command("test"), F.chat.type == "private")
async def test_command(message: Message, command: CommandObject, api: VocabAPI, cfg: Settings) -> None:
    if not command.args:
        await message.answer("Пришли /test и текст контрольной в одном сообщении или файл .docx.")
        return
    classes = await _teacher_classes(message, api)
    if classes is None:
        return
    title = f"Контрольная {datetime.now(ZoneInfo(cfg.tz)):%d.%m}"
    await _offer(message, api, classes, command.args, title)


@router.message(F.document.file_name.lower().endswith(".docx"), F.chat.type == "private")
async def test_docx(message: Message, bot: Bot, api: VocabAPI) -> None:
    classes = await _teacher_classes(message, api)
    if classes is None:
        return
    file = await bot.download(message.document)
    try:
        text = classwork.docx_text(file.getvalue())
    except classwork.QuestionError:
        await message.answer("Это не файл Word (.docx).")
        return
    await _offer(message, api, classes, text, Path(message.document.file_name).stem[:120])


@router.callback_query(F.data.startswith("exam:"))
async def start_exam(callback: CallbackQuery, api: VocabAPI) -> None:
    _, class_id, minutes = callback.data.split(":")
    draft = pending.get(callback.from_user.id)
    if draft is None:
        await callback.answer("Пришли контрольную ещё раз", show_alert=True)
        return
    try:
        await api.start_live_test(callback.from_user.id, int(class_id), *draft, int(minutes))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 409:
            raise
        await callback.answer("К классу не привязана группа", show_alert=True)
        return
    del pending[callback.from_user.id]
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Запущено в группе ✅")


@router.callback_query(F.data.startswith("examstop:"))
async def stop_exam(callback: CallbackQuery, api: VocabAPI) -> None:
    test_id = int(callback.data.split(":", 1)[1])
    try:
        await api.finish_test(callback.from_user.id, test_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (403, 404):
            raise
        await callback.answer("Закончить может учитель", show_alert=True)
        return
    await callback.answer("Время вышло, итоги через минуту")


async def post_summaries(bot: Bot, api: VocabAPI) -> None:
    """Итоги закончившихся контрольных в группу. API помечает их при выдаче,
    поэтому неотправленное повторно не придёт — только в лог."""
    for summary in await api.test_summaries():
        link = f"https://t.me/{(await bot.me()).username}?startapp=test_{summary['test_id']}"
        button = InlineKeyboardButton(text="Мой разбор", url=link)
        try:
            await bot.send_message(
                summary["chat_id"], summary_text(summary),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            )
        except Exception as exc:  # noqa: BLE001 — остальным группам итоги дойти должны
            log.warning("не отправил итоги теста %s в группу %s: %s", summary["test_id"], summary["chat_id"], exc)
