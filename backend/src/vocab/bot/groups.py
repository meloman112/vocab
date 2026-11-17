"""Класс в группе Telegram: привязка, вход, помощник, домашка, отчёт.

Бот отвечает только в группе и никому не пишет в личку. Кнопки с web_app
в группах не работают, поэтому тетрадь открывается ссылкой ?startapp=.
"""

import re
from typing import Any

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, User,
)

from ..client import VocabAPI
from .reminders import item_label

router = Router()
GROUP = F.chat.type.in_({"group", "supergroup"})
router.message.filter(GROUP)
router.callback_query.filter(F.message.chat.type.in_({"group", "supergroup"}))

# Должно совпадать с api/groups.py: оба ответа «не найдено» различаются только текстом.
UNBOUND = "группа не привязана к классу"
UNBOUND_TEXT = "Группа не привязана к классу. Привязать: /bind"
JOIN_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎒 Я в классе", callback_data="join")]])
RANGE = re.compile(r"(\d+)(?:\s*[-–]\s*(\d+))?")
MAX_RANGE = 200


def parse_exercises(text: str) -> list[int]:
    """«26-28, 31» → [26, 27, 28, 31]."""
    numbers: set[int] = set()
    for first, last in RANGE.findall(text):
        start = int(first)
        numbers.update(range(start, min(int(last or first), start + MAX_RANGE) + 1))
    return sorted(numbers)


def _list(exercises: list[int]) -> str:
    return ", ".join(map(str, exercises))


def report_text(report: dict[str, Any]) -> str:
    total = report["total"]
    lines = [f"📊 Домашка: упражнения {_list(report['exercises'])} ({total} заданий)", ""]
    for s in sorted(report["students"], key=lambda s: -s["done"]):
        if not s["done"]:
            lines.append(f"• {s['name']} — не начинал")
            continue
        line = (f"• {s['name']} — {s['done']} из {total}, с первого раза {s['first_try']}"
                f" ({round(100 * s['first_try'] / s['done'])}%)")
        if s["top_mistake"]:
            line += f", чаще всего: {s['top_mistake']} ×{s['top_count']}"
        lines.append(line)
    if report["hard_items"]:
        lines += ["", "Трудные задания:"]
        lines += [f"{item_label(i['item'])} — ошиблись {i['students']}" for i in report["hard_items"]]
    return "\n".join(lines)


def _error_text(exc: httpx.HTTPStatusError, texts: dict[int, str]) -> str:
    """Текст для известной ошибки API; неизвестная падает как есть."""
    code = exc.response.status_code
    detail = exc.response.json().get("detail")
    if code == 404 and detail == UNBOUND:
        return UNBOUND_TEXT
    if code == 422:
        return detail
    if code not in texts:
        raise exc
    return texts[code]


async def _bind(user: User, chat_id: int, title: str, api: VocabAPI, class_id: int | None = None):
    result = await api.bind_group(user.id, user.full_name, chat_id, title, class_id)
    if result["bound"] is None:
        rows = [[InlineKeyboardButton(text=c["name"][:60], callback_data=f"bind:{c['id']}")] for c in result["classes"]]
        return "К какому классу привязать группу?", InlineKeyboardMarkup(inline_keyboard=rows)
    return (f"Группа привязана к классу «{result['bound']}». Нажмите кнопку, чтобы войти в класс.",
            JOIN_KEYBOARD)


TAKEN = {403: "Группа уже привязана к классу другого учителя."}


@router.message(Command("bind"))
async def bind(message: Message, api: VocabAPI) -> None:
    try:
        text, keyboard = await _bind(message.from_user, message.chat.id, message.chat.title, api)
    except httpx.HTTPStatusError as exc:
        await message.answer(_error_text(exc, TAKEN))
        return
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("bind:"))
async def bind_choice(callback: CallbackQuery, api: VocabAPI) -> None:
    chat = callback.message.chat
    try:
        text, keyboard = await _bind(callback.from_user, chat.id, chat.title, api,
                                     int(callback.data.split(":", 1)[1]))
    except httpx.HTTPStatusError as exc:
        await callback.answer(_error_text(exc, TAKEN), show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "join")
async def join(callback: CallbackQuery, api: VocabAPI) -> None:
    user = callback.from_user
    try:
        result = await api.join_group(user.id, user.full_name, callback.message.chat.id)
    except httpx.HTTPStatusError as exc:
        await callback.answer(_error_text(exc, {}), show_alert=True)
        return
    text = f"Ты в классе «{result['class_name']}»" if result["joined"] else "Ты уже в классе"
    await callback.answer(text, show_alert=True)


@router.message(Command("helper"))
async def helper(message: Message, api: VocabAPI) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if target is None:
        await message.answer("Ответь этой командой на сообщение ученика.")
        return
    if target.is_bot:
        return
    user = message.from_user
    try:
        result = await api.toggle_assistant(
            user.id, user.full_name, message.chat.id, target.id, target.full_name[:64])
    except httpx.HTTPStatusError as exc:
        await message.answer(_error_text(exc, {403: "Помощника назначает учитель."}))
        return
    if result["assistant"]:
        await message.answer(f"{target.full_name} теперь помощник: может задавать домашку (/dz) и вызывать отчёт (/report).")
        return
    await message.answer(f"{target.full_name} больше не помощник.")


async def _homework_post(message: Message, bot: Bot, homework: dict[str, Any]) -> None:
    me = await bot.me()
    button = InlineKeyboardButton(text="Открыть тетрадь", url=f"https://t.me/{me.username}?startapp=grammar")
    await message.answer(
        f"📒 Домашка: упражнения {_list(homework['exercises'])} ({homework['items']} заданий)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )


@router.message(Command("dz"))
async def dz(message: Message, command: CommandObject, api: VocabAPI, bot: Bot) -> None:
    user = message.from_user
    exercises = parse_exercises(command.args or "")
    if command.args and not exercises:
        await message.answer("Не понял номера. Пример: /dz 26-28, 31")
        return
    try:
        if exercises:
            homework = await api.set_homework(user.id, user.full_name, message.chat.id, exercises)
        else:
            homework = await api.homework(user.id, user.full_name, message.chat.id)
    except httpx.HTTPStatusError as exc:
        texts = {403: "Домашку задаёт учитель или помощник.", 404: "Домашки пока нет. Задать: /dz 26-28"}
        await message.answer(_error_text(exc, texts))
        return
    await _homework_post(message, bot, homework)


@router.message(Command("report"))
async def report(message: Message, api: VocabAPI) -> None:
    user = message.from_user
    try:
        data = await api.homework_report(user.id, user.full_name, message.chat.id)
    except httpx.HTTPStatusError as exc:
        texts = {403: "Отчёт вызывает учитель или помощник.", 404: "Сначала задайте домашку: /dz 26-28"}
        await message.answer(_error_text(exc, texts))
        return
    await message.answer(report_text(data))
