"""Тетрадь и учителя в боте. Роутер подключается раньше основного: там
последний хендлер принимает любой текст за слово на добавление."""

import logging

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ..client import VocabAPI
from ..config import Settings

log = logging.getLogger(__name__)
router = Router()
router.message.filter(F.chat.type == "private")

CLASS_PREFIX = "class_"


def screen_button(cfg: Settings, text: str, screen: str) -> InlineKeyboardButton:
    """Кнопка, открывающая мини-апп сразу на нужном экране."""
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen={screen}"))


def test_keyboard(cfg: Settings, test_id: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(text="Открыть тест", web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen=test&id={test_id}"))
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


TEACHING = (
    "👩‍🏫 Класс создаётся в приложении, на вкладке «Класс». Или добавь меня в группу "
    "Telegram и отправь там /bind — группа станет классом.\n"
    "Разошли ученикам ссылку класса: кто её откроет, тот в классе, и ты видишь "
    "его тетрадь и ошибки.\n"
    "/test — контрольная на уроке, /students — сводка по ученикам."
)


def teaching_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "👩‍🏫 Открыть класс", "teacher")]])


def grammar_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "📒 Открыть тетрадь", "grammar")]])


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(CLASS_PREFIX)))
async def join_class(message: Message, command: CommandObject, api: VocabAPI, cfg: Settings, bot: Bot) -> None:
    """t.me/<bot>?start=class_<code> — ссылка класса, которую учитель раздал ученикам."""
    code = (command.args or "").removeprefix(CLASS_PREFIX)
    user = message.from_user
    try:
        result = await api.join_class(user.id, user.full_name, code)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        await message.answer("Такого класса нет. Попроси у учителя ссылку ещё раз.")
        return
    await message.answer(
        f"Ты в классе «{result['class_name']}» 🎒 Учитель: {result['teacher']}.\n\n"
        "Тесты от учителя придут сюда, в бот. Открытые тесты — в мини-аппе, раздел «Тесты».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "📝 Мои тесты", "tests")]]),
    )
    if result["joined"] and result["teacher_tg_id"] != user.id:
        try:
            await bot.send_message(result["teacher_tg_id"], f"{user.full_name} теперь в классе «{result['class_name']}».")
        except Exception as exc:  # noqa: BLE001 — уведомление не должно ронять вход в класс
            log.warning("не сообщил учителю %s о новом ученике: %s", result["teacher_tg_id"], exc)


@router.message(Command("grammar"))
async def grammar(message: Message, cfg: Settings) -> None:
    await message.answer(
        "Тетрадь: 134 упражнения из Work book — от Present Simple до Participle. "
        "Ошибки разбираются сразу, а учитель видит, где ты споткнулся.",
        reply_markup=grammar_keyboard(cfg),
    )


def _teachers_view(teachers: list[dict]) -> tuple[str, InlineKeyboardMarkup | None]:
    lines = ["👩‍🏫 Учителем становится каждый, кто создал класс.", "",
             "Сейчас учителя:" if teachers else "Учителей пока нет."]
    lines += [f"• {t['name']}" for t in teachers]
    rows = [
        [InlineKeyboardButton(text=f"✖️ Снять: {t['name']}"[:60], callback_data=f"unteach:{t['user_id']}")]
        for t in teachers
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


@router.message(Command("teacher"))
async def teacher(message: Message, api: VocabAPI, cfg: Settings) -> None:
    """Админу — список учителей, остальным — как завести класс."""
    if not cfg.is_admin(message.from_user.id):
        await message.answer(TEACHING, reply_markup=teaching_keyboard(cfg))
        return
    text, keyboard = _teachers_view(await api.teachers(message.from_user.id))
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("unteach:"))
async def unteach(callback: CallbackQuery, api: VocabAPI, cfg: Settings) -> None:
    if not cfg.is_admin(callback.from_user.id):
        await callback.answer("Только для админа", show_alert=True)
        return
    user_id = int(callback.data.split(":", 1)[1])
    try:
        await api.remove_teacher(callback.from_user.id, user_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    await callback.answer("Снят")
    text, keyboard = _teachers_view(await api.teachers(callback.from_user.id))
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.message(Command("students"))
async def students(message: Message, api: VocabAPI, cfg: Settings) -> None:
    """Сводка учителю: кто занимался и у кого неразобранные ошибки."""
    try:
        rows = await api.students(message.from_user.id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 403:
            raise
        await message.answer("Это для учителей. /teacher — как завести класс.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "👩‍🏫 Открыть учеников", "teacher")]])
    if not rows:
        await message.answer("Никто из учеников тетрадь пока не делал.", reply_markup=keyboard)
        return
    lines = [
        f"• {r['name']} — сделано {r['done']}, с первого раза {r['first_try']}"
        + (f", ❗ ошибок: {r['mistakes']}" if r["mistakes"] else "")
        for r in rows[:30]
    ]
    await message.answer("Ученики тетради:\n\n" + "\n".join(lines), reply_markup=keyboard)
