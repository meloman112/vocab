"""Хендлеры бота. Логики нет: всё через API, бот — просто ещё один клиент."""

import logging
from typing import Any

import httpx
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ..client import VocabAPI
from ..config import Settings

log = logging.getLogger(__name__)
router = Router()

MAX_TEXT_LEN = 300

# Пороги шкалы Zipf (wordfreq): 6+ — the, have; 5 — read, child;
# 4 — reliable; 3 — redundant; ниже — редкость.
FREQUENCY_LABELS = (
    (6.0, "очень частое"),
    (5.0, "частое"),
    (4.0, "среднее"),
    (3.0, "редкое"),
)


def review_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🧠 Повторять", web_app=WebAppInfo(url=cfg.miniapp_url)
            )
        ]]
    )


def frequency_label(zipf: float) -> str:
    for threshold, label in FREQUENCY_LABELS:
        if zipf >= threshold:
            return label
    return "очень редкое"


def format_entry(entry: dict[str, Any]) -> str:
    head = f"📖 {entry['lemma']}  /{entry['ipa']}/ — {entry['pos']}"
    if entry["irregular"]:
        head += " ⚠️ неправильное"
    lines = [head]
    if entry["form_note"]:
        lines.append(f"ты прислал форму: {entry['form_note']}")
    if entry["forms"]:
        lines.append(entry["forms"])
    lines.append("")
    lines.append(entry["translation"])
    lines += [f"• {e['en']} — {e['ru']}" for e in entry["examples"]]
    lines.append("")
    lines.append(f"⭐ {frequency_label(entry['zipf'])} · учат: {entry['learners']}")
    lines.append("✅ добавлено в твои слова" if entry["created"] else "уже было в твоих словах")
    return "\n".join(lines)


@router.message(Command("start"))
async def start(message: Message, cfg: Settings) -> None:
    await message.answer(
        "Пришли английское слово в любой форме — went, children, reading — "
        "отвечу переводом, формой и примерами и добавлю в повторение.\n"
        "Пришлёшь фразу или предложение — достану из него устойчивые выражения.\n\n"
        "/review — повторение\n/stats — цифры",
        reply_markup=review_keyboard(cfg),
    )


@router.message(Command("review"))
async def review(message: Message, cfg: Settings) -> None:
    await message.answer("Погнали:", reply_markup=review_keyboard(cfg))


@router.message(Command("stats"))
async def stats(message: Message, api: VocabAPI) -> None:
    # from_user, а не chat: в группе chat.id — идентификатор группы,
    # и словарь завёлся бы на неё, а не на человека.
    data = await api.stats(message.from_user.id)
    forecast = " ".join(f"{d['count']}" for d in data["forecast"])
    await message.answer(
        f"Всего: {data['total']}\n"
        f"Выучено: {data['learned']}\n"
        f"Сейчас на повторение: {data['due_now']}\n"
        f"Сегодня всего: {data['due_today']}\n"
        f"Прогноз на 7 дней: {forecast}"
    )


@router.message(Command("ban"))
async def ban(message: Message, command: CommandObject, api: VocabAPI, cfg: Settings) -> None:
    """Убрать мусор из общего словаря. Только владельцу."""
    if message.from_user.id != cfg.owner_tg_id:
        return
    if not command.args:
        await message.answer("/ban слово")
        return
    try:
        await api.ban(command.args)
    except httpx.HTTPStatusError as exc:
        await message.answer(exc.response.json()["detail"])
        return
    await message.answer(f"«{command.args}» убрано из словаря")


@router.message(F.text)
async def add_word(message: Message, api: VocabAPI) -> None:
    """Любое текстовое сообщение — слово или фраза на добавление.

    Ограничение по длине здесь, а не только в API: иначе на случайно
    вставленный абзац пользователь получил бы 422 без объяснения.
    """
    text = message.text.strip()
    if len(text) > MAX_TEXT_LEN:
        await message.answer("Слишком длинно. Пришли слово, фразу или одно предложение.")
        return

    # Новое слово ждёт ответа ИИ несколько секунд — пусть видно, что бот жив.
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        entries = await api.add_word(message.from_user.id, text)
    except httpx.HTTPStatusError as exc:
        # 422 и 502 несут текст для человека; всё остальное — настоящая
        # ошибка, и пусть падает в лог aiogram.
        if exc.response.status_code not in (422, 502):
            raise
        await message.answer(exc.response.json()["detail"])
        return

    for entry in entries:
        await message.answer(format_entry(entry))
