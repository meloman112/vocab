"""Хендлеры бота. Логики нет: всё через API, бот — просто ещё один клиент."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
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

MAX_WORD_LEN = 100


def review_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🧠 Повторять", web_app=WebAppInfo(url=cfg.miniapp_url)
            )
        ]]
    )


@router.message(Command("start"))
async def start(message: Message, cfg: Settings) -> None:
    await message.answer(
        "Пришли английское слово — оно попадёт в словарь, перевод догонит.\n\n"
        "/review — повторение\n/stats — цифры\n/failed — что не обогатилось",
        reply_markup=review_keyboard(cfg),
    )


@router.message(Command("review"))
async def review(message: Message, cfg: Settings) -> None:
    await message.answer("Погнали:", reply_markup=review_keyboard(cfg))


@router.message(Command("stats"))
async def stats(message: Message, api: VocabAPI) -> None:
    data = await api.stats(message.chat.id)
    forecast = " ".join(f"{d['count']}" for d in data["forecast"])
    await message.answer(
        f"Всего: {data['total']}\n"
        f"Выучено: {data['learned']}\n"
        f"Сейчас на повторение: {data['due_now']}\n"
        f"Сегодня всего: {data['due_today']}\n"
        f"В обработке: {data['pending']}, не удалось: {data['failed']}\n"
        f"Прогноз на 7 дней: {forecast}"
    )


@router.message(Command("failed"))
async def failed(message: Message, api: VocabAPI) -> None:
    cards = await api.failed(message.chat.id)
    if not cards:
        await message.answer("Все карточки обогатились.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔁 {c['word']}", callback_data=f"retry:{c['id']}")]
            for c in cards
        ]
    )
    await message.answer("Не обогатились — нажми, чтобы повторить:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("retry:"))
async def retry(callback: CallbackQuery, api: VocabAPI) -> None:
    card_id = int(callback.data.split(":", 1)[1])
    await api.retry(callback.from_user.id, card_id)
    await callback.answer("Отправил на обогащение")


@router.message(F.text)
async def add_word(message: Message, api: VocabAPI) -> None:
    """Любое текстовое сообщение — слово на добавление.

    Ограничение по длине здесь, а не только в API: иначе на случайно
    вставленный абзац пользователь получил бы 422 без объяснения.
    """
    word = message.text.strip()
    if len(word) > MAX_WORD_LEN:
        await message.answer("Это больше похоже на текст, чем на слово.")
        return

    result = await api.add_word(message.chat.id, word)
    await message.answer("✅ added" if result["created"] else "уже есть")
