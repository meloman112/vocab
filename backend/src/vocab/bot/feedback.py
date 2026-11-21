"""Ответы на отзывы. API присылает админу сообщение пользователя и черновик
ответа от ИИ с кнопками; здесь решение админа уходит обратно в API.
Роутер подключается раньше основного: там любой текст — слово на добавление."""

import html

import httpx
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..client import VocabAPI
from ..config import Settings

router = Router()
router.message.filter(F.chat.type == "private")


class Reply(StatesGroup):
    writing = State()


def _closed(exc: httpx.HTTPStatusError) -> str:
    """Отказ API — текстом для админа; незнакомая ошибка летит дальше."""
    if exc.response.status_code in (409, 422, 502):
        return exc.response.json()["detail"]
    raise exc


async def _mark(callback: CallbackQuery, note: str) -> None:
    """Под черновиком — итог, кнопки убираются: второй раз не нажать."""
    await callback.message.edit_text(f"{callback.message.text}\n\n{note}", reply_markup=None)


@router.callback_query(F.data.startswith("fb:"))
async def decide(callback: CallbackQuery, api: VocabAPI, cfg: Settings, state: FSMContext) -> None:
    if not cfg.is_admin(callback.from_user.id):
        await callback.answer("Только для админа", show_alert=True)
        return
    _, action, raw_id = callback.data.split(":")
    feedback_id = int(raw_id)
    if action == "edit":
        await state.set_state(Reply.writing)
        await state.update_data(feedback_id=feedback_id, draft_message=callback.message.message_id)
        await callback.answer()
        draft = callback.message.text.partition("\n\n")[2] if callback.message.text.startswith("✍️") else ""
        hint = f"\n\nЧерновик — нажми, чтобы скопировать:\n<code>{html.escape(draft)}</code>" if draft else ""
        await callback.message.answer(f"Напиши ответ #{feedback_id} — уйдёт как есть. /cancel — передумал.{hint}",
                                      parse_mode="HTML")
        return
    try:
        if action == "send":
            await api.answer_feedback(callback.from_user.id, feedback_id)
        else:
            await api.skip_feedback(callback.from_user.id, feedback_id)
    except httpx.HTTPStatusError as exc:
        await callback.answer(_closed(exc), show_alert=True)
        return
    await callback.answer("Отправлено" if action == "send" else "Закрыто")
    await _mark(callback, "✅ Отправлено" if action == "send" else "🚫 Без ответа")


@router.message(StateFilter(Reply.writing), Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ок, не отправляю. Кнопки под черновиком остались.")


@router.message(StateFilter(Reply.writing), F.text)
async def write(message: Message, api: VocabAPI, state: FSMContext) -> None:
    data = await state.get_data()
    feedback_id = data["feedback_id"]
    try:
        await api.answer_feedback(message.from_user.id, feedback_id, message.text)
    except httpx.HTTPStatusError as exc:
        await state.clear()
        await message.answer(f"Не отправлено: {_closed(exc)}")
        return
    await state.clear()
    # Кнопки под черновиком больше не нужны: ответ уже ушёл.
    await message.bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=data["draft_message"])
    await message.answer(f"✅ Ответ #{feedback_id} отправлен.")
