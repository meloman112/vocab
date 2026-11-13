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
from . import chat
from .widget import Widgets

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
                text="🧠 Повторять", web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen=cards")
            )
        ]]
    )


def entry_keyboard(entry: dict[str, Any]) -> InlineKeyboardMarkup:
    """Кнопки других частей речи той же леммы (под «a book — книга»
    предлагается «to book — бронировать») и жалоба на слово."""
    rows = []
    for other in entry["others"]:
        data = f"sense:{other['pos']}:{entry['lemma']}"
        if len(data.encode()) > MAX_CALLBACK:
            continue
        form, name = POS_LABELS.get(other["pos"], ("{}", other["pos"]))
        meaning = other["translation"] or name
        text = f"➕ {form.format(entry['lemma'])} — {meaning}"
        rows.append(_callback(text, data))
    rows.append(_callback("⚠️ Ошибка в слове", f"report:{entry['id']}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


REPORT_REASONS = {
    "typo": "Опечатка, нет такого слова",
    "translation": "Неверный перевод",
    "example": "Плохой пример",
}


def _callback(text: str, data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text[:60], callback_data=data)]


async def add_and_reply(
    message: Message, tg_id: int, api: VocabAPI, widgets: Widgets, text: str,
    pos: str | None = None, as_is: bool = False,
) -> None:
    """Добавление и ответ. Отказ API превращается в текст для человека,
    опечатка — ещё и в кнопки «help» / «добавить как есть»."""
    # Новое слово ждёт ответа ИИ несколько секунд — пусть видно, что бот жив.
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        entries = await api.add_word(tg_id, text, pos, as_is)
    except httpx.HTTPStatusError as exc:
        # 422 и 502 несут текст для человека; всё остальное — настоящая
        # ошибка, и пусть падает в лог aiogram.
        if exc.response.status_code not in (422, 502):
            raise
        detail = exc.response.json()["detail"]
        if isinstance(detail, str):
            sent = await message.answer(detail)
            widgets.track(message.chat.id, "card", sent.message_id)
            return
        rows = [_callback(f"➕ {detail['suggestion']}", f"add:{detail['suggestion']}")]
        if len(f"asis:{text}".encode()) <= MAX_CALLBACK:
            rows.append(_callback(f"Нет, именно «{text}»", f"asis:{text}"))
        sent = await message.answer(detail["message"], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        widgets.track(message.chat.id, "card", sent.message_id)
        return
    for entry in entries:
        await widgets.send(message.chat.id, "card", chat.card_data(entry), keyboard=entry_keyboard(entry))


@router.message(Command("start"))
async def start(message: Message, cfg: Settings, widgets: Widgets) -> None:
    await message.answer(
        "Привет! Здесь два раздела.\n\n"
        "📒 Тетрадь — 134 упражнения по грамматике из Work book: времена, Passive, "
        "Conditionals, Relative clauses, Gerund, модальные глаголы, Participle. "
        "Каждую ошибку бот разбирает, а учитель видит, где ты споткнулся.\n\n"
        "🧠 Слова — пришли английское слово в любой форме (went, children, reading): "
        "отвечу переводом, формой и примерами и добавлю в повторение. "
        "Части речи уточняй так: to book (бронировать), a book (книга). "
        "Из фразы или предложения достану устойчивые выражения.\n\n"
        "Прямо в чате: ⚡ разминка каждые пару часов, 🎯 /quiz — тест, "
        "🔁 /verbs — неправильные глаголы на скорость, 📊 /stats — табло (закреплено сверху).\n\n"
        "/grammar — тетрадь\n/review — повторение в приложении\n"
        "/top — что учат чаще всего\n/rating — рейтинг недели",
    )
    await chat.send_board(widgets, cfg, message.chat.id)


@router.message(Command("review"))
async def review(message: Message, cfg: Settings) -> None:
    await message.answer("Погнали:", reply_markup=review_keyboard(cfg))


@router.message(Command("stats"))
async def stats(message: Message, cfg: Settings, widgets: Widgets) -> None:
    """Табло: цифры и кнопки разминки, теста и игры."""
    await message.delete()
    await chat.send_board(widgets, cfg, message.chat.id)


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


async def open_widget(message: Message, api: VocabAPI, widgets: Widgets, kind: str) -> None:
    """Команда виджета: сама команда из чата убирается, виджет — вместо прежнего."""
    await message.delete()
    if not await chat.OPENERS[kind](widgets, api, message.chat.id):
        await message.answer(chat.EMPTY[kind])


@router.message(Command("quiz"))
async def quiz(message: Message, api: VocabAPI, widgets: Widgets) -> None:
    await open_widget(message, api, widgets, "quiz")


@router.message(Command("verbs"))
async def verbs(message: Message, api: VocabAPI, widgets: Widgets) -> None:
    await open_widget(message, api, widgets, "verbs")


@router.message(Command("warmup"))
async def warmup(message: Message, api: VocabAPI, widgets: Widgets) -> None:
    await open_widget(message, api, widgets, "warmup")


@router.message(F.text)
async def add_word(message: Message, api: VocabAPI, widgets: Widgets) -> None:
    """Любое текстовое сообщение — слово или фраза на добавление.

    Прошлое слово с его карточкой из чата убирается: остаётся только
    текущее, чат не превращается в ленту.

    Ограничение по длине здесь, а не только в API: иначе на случайно
    вставленный абзац пользователь получил бы 422 без объяснения.
    """
    await widgets.clean(message.chat.id, "card")
    widgets.track(message.chat.id, "card", message.message_id)
    text = message.text.strip()
    if len(text) > MAX_TEXT_LEN:
        await message.answer("Слишком длинно. Пришли слово, фразу или одно предложение.")
        return
    await add_and_reply(message, message.from_user.id, api, widgets, text)


@router.callback_query(F.data.startswith("sense:"))
async def add_sense(callback: CallbackQuery, api: VocabAPI, widgets: Widgets) -> None:
    """Кнопка «➕ to book»: то же добавление, но с выбранной частью речи."""
    _, pos, lemma = callback.data.split(":", 2)
    # Отвечаем сразу: новое значение ждёт ИИ дольше, чем Telegram ждёт ответа
    # на нажатие, и у пользователя повисли бы часики на кнопке.
    await callback.answer()
    await add_and_reply(callback.message, callback.from_user.id, api, widgets, lemma, pos)


@router.callback_query(F.data.startswith("add:"))
async def add_suggestion(callback: CallbackQuery, api: VocabAPI, widgets: Widgets) -> None:
    """«➕ help» под «Слова helf нет. Может, help?»."""
    await callback.answer()
    await add_and_reply(callback.message, callback.from_user.id, api, widgets, callback.data[4:])


@router.callback_query(F.data.startswith("asis:"))
async def add_as_is(callback: CallbackQuery, api: VocabAPI, widgets: Widgets) -> None:
    await callback.answer()
    await add_and_reply(callback.message, callback.from_user.id, api, widgets, callback.data[5:], as_is=True)


@router.callback_query(F.data.startswith("report:"))
async def report_menu(callback: CallbackQuery) -> None:
    """«⚠️ Ошибка в слове» → что именно не так."""
    word_id = callback.data.split(":", 1)[1]
    rows = [_callback(text, f"rep:{reason}:{word_id}") for reason, text in REPORT_REASONS.items()]
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("rep:"))
async def report(callback: CallbackQuery, api: VocabAPI) -> None:
    _, reason, word_id = callback.data.split(":", 2)
    await api.report(callback.from_user.id, int(word_id), reason)
    await callback.answer("Спасибо! Передал админу.")
    await callback.message.edit_reply_markup(reply_markup=None)
