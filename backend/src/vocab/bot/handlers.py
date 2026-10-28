"""Хендлеры бота. Логики нет: всё через API, бот — просто ещё один клиент."""

import logging
from typing import Any

import httpx
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from ..client import VocabAPI
from ..config import Settings

log = logging.getLogger(__name__)
router = Router()

MAX_TEXT_LEN = 300

# Как назвать другое значение леммы на кнопке: «to book», «a book».
POS_LABELS = {
    "noun": ("a {}", "существительное"),
    "verb": ("to {}", "глагол"),
    "adjective": ("{}", "прилагательное"),
    "adverb": ("{}", "наречие"),
}
# Telegram режет callback_data на 64 байтах.
MAX_CALLBACK = 64


def review_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🧠 Повторять", web_app=WebAppInfo(url=cfg.miniapp_url)
            )
        ]]
    )


def format_entry(entry: dict[str, Any]) -> str:
    head = f"📖 {entry['lemma']}  /{entry['ipa']}/ — {entry['pos']}"
    if entry["irregular"]:
        head += " ⚠️ неправильное"
    lines = [head]
    if entry["form_note"]:
        lines.append(f"🔤 {entry['form_note']}")
    if entry["forms"]:
        lines.append(entry["forms"])
    lines.append("")
    lines.append(entry["translation"])
    lines += [f"• {e['en']} — {e['ru']}" for e in entry["examples"]]
    lines.append("")
    lines.append(f"⭐ {entry['top']} · учат: {entry['learners']}")
    lines.append("✅ добавлено в твои слова" if entry["created"] else "уже было в твоих словах")
    return "\n".join(lines)


def senses_keyboard(entry: dict[str, Any]) -> InlineKeyboardMarkup | None:
    """Кнопки других частей речи той же леммы: под «a book — книга»
    предлагается «to book — бронировать»."""
    rows = []
    for other in entry["others"]:
        data = f"sense:{other['pos']}:{entry['lemma']}"
        if len(data.encode()) > MAX_CALLBACK:
            continue
        form, name = POS_LABELS.get(other["pos"], ("{}", other["pos"]))
        meaning = other["translation"] or name
        text = f"➕ {form.format(entry['lemma'])} — {meaning}"
        rows.append([InlineKeyboardButton(text=text[:60], callback_data=data)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def send_entries(message: Message, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        await message.answer(format_entry(entry), reply_markup=senses_keyboard(entry))


@router.message(Command("start"))
async def start(message: Message, cfg: Settings) -> None:
    await message.answer(
        "Пришли английское слово в любой форме — went, children, reading — "
        "отвечу переводом, формой и примерами и добавлю в повторение.\n"
        "Слово бывает разными частями речи — уточни: to book (бронировать), "
        "a book (книга).\n"
        "Пришлёшь фразу или предложение — достану из него устойчивые выражения.\n\n"
        "/review — повторение\n/stats — цифры и серия\n/top — что учат чаще всего\n"
        "/rating — рейтинг недели",
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
        f"Прогноз на 7 дней: {forecast}\n"
        f"🔥 Серия: {data['streak']} дн. (рекорд {data['best_streak']})"
    )


@router.message(Command("top"))
async def top(message: Message, api: VocabAPI) -> None:
    words = await api.top(message.from_user.id)
    if not words:
        await message.answer("Общий словарь пока пуст.")
        return
    lines = [
        f"{i}. {w['word']} — {w['translation']}  ⭐ {w['top']} · учат: {w['learners']}"
        + (" ✅" if w["mine"] else "")
        for i, w in enumerate(words, 1)
    ]
    await message.answer("Что учат чаще всего (✅ — есть у тебя):\n\n" + "\n".join(lines))


@router.message(Command("rating"))
async def rating(message: Message, api: VocabAPI) -> None:
    board = await api.leaderboard(message.from_user.id)
    if not board["top"]:
        await message.answer("На этой неделе ещё никто не занимался. Будь первым!")
        return
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [
        f"{medals.get(r['place'], str(r['place']) + '.')} {r['name']} — {r['xp']} XP"
        + (f" 🔥{r['streak']}" if r["streak"] else "")
        for r in board["top"]
    ]
    me = board["me"]
    footer = (
        f"Ты: {me['place']} место, {me['xp']} XP"
        if me
        else "Тебя пока нет в рейтинге — одно повторение, и ты в списке."
    )
    await message.answer(
        "🏆 Рейтинг недели (10 XP за повторение, обнуляется в понедельник)\n\n"
        + "\n".join(lines) + "\n\n" + footer
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

    await send_entries(message, entries)


@router.callback_query(F.data.startswith("sense:"))
async def add_sense(callback: CallbackQuery, api: VocabAPI) -> None:
    """Кнопка «➕ to book»: то же добавление, но с выбранной частью речи."""
    _, pos, lemma = callback.data.split(":", 2)
    # Отвечаем сразу: новое значение ждёт ИИ дольше, чем Telegram ждёт ответа
    # на нажатие, и у пользователя повисли бы часики на кнопке.
    await callback.answer()
    await callback.message.bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
    try:
        entries = await api.add_word(callback.from_user.id, lemma, pos)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (422, 502):
            raise
        await callback.message.answer(exc.response.json()["detail"])
        return
    await send_entries(callback.message, entries)
