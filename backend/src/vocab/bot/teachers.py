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

INVITE_PREFIX = "teach_"
CLASS_PREFIX = "class_"


def screen_button(cfg: Settings, text: str, screen: str) -> InlineKeyboardButton:
    """Кнопка, открывающая мини-апп сразу на нужном экране."""
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen={screen}"))


def test_keyboard(cfg: Settings, test_id: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(text="Открыть тест", web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen=test&id={test_id}"))
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def grammar_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "📒 Открыть тетрадь", "grammar")]])


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(INVITE_PREFIX)))
async def redeem(message: Message, command: CommandObject, api: VocabAPI, cfg: Settings, bot: Bot) -> None:
    """t.me/<bot>?start=teach_<code> — ссылка, которую админ отдал учителю."""
    code = (command.args or "").removeprefix(INVITE_PREFIX)
    user = message.from_user
    try:
        result = await api.redeem_teacher_invite(user.id, user.full_name, code)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 410:
            raise
        await message.answer("Ссылка уже использована или устарела. Попроси новую у админа.")
        return
    await message.answer(
        "Готово, теперь ты учитель 🎓\n\n"
        "В мини-аппе появился раздел «Ученики»: там видно, кто что сделал в тетради, "
        "какие ответы были неверными и почему. Если ученик ответил правильно, а ключ "
        "этого не знал, — нажми «Засчитать», и ответ будет приниматься у всех.\n\n"
        "/students — короткая сводка прямо в чате.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "👩‍🏫 Ученики", "teacher")]]),
    )
    inviter = result.get("inviter_tg_id")
    if inviter and inviter != user.id:
        try:
            await bot.send_message(inviter, f"{user.full_name} теперь учитель.")
        except Exception as exc:  # noqa: BLE001 — уведомление не должно ронять назначение
            log.warning("не сообщил %s о новом учителе: %s", inviter, exc)


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


def _teachers_view(teachers: list[dict], link: str | None) -> tuple[str, InlineKeyboardMarkup | None]:
    lines = ["👩‍🏫 Учителя видят ошибки всех учеников тетради и могут засчитывать ответы."]
    if link:
        lines += ["", "Перешли эту ссылку учителю — она одноразовая и живёт 7 дней:", link]
    lines += ["", "Сейчас учителя:" if teachers else "Учителей пока нет."]
    lines += [f"• {t['name']}" for t in teachers]
    rows = [
        [InlineKeyboardButton(text=f"✖️ Снять: {t['name']}"[:60], callback_data=f"unteach:{t['user_id']}")]
        for t in teachers
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


@router.message(Command("teacher"))
async def teacher(message: Message, api: VocabAPI, cfg: Settings, bot: Bot) -> None:
    """Только админам: ссылка-приглашение для учителя и список учителей."""
    if not cfg.is_admin(message.from_user.id):
        await message.answer("Учителей назначает админ. Если ты учитель — попроси у него ссылку.")
        return
    invite = await api.create_teacher_invite(message.from_user.id)
    me = await bot.me()
    link = f"https://t.me/{me.username}?start={INVITE_PREFIX}{invite['code']}"
    text, keyboard = _teachers_view(await api.teachers(message.from_user.id), link)
    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


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
    text, keyboard = _teachers_view(await api.teachers(callback.from_user.id), None)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.message(Command("students"))
async def students(message: Message, api: VocabAPI, cfg: Settings) -> None:
    """Сводка учителю: кто занимался и у кого неразобранные ошибки."""
    try:
        rows = await api.students(message.from_user.id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 403:
            raise
        await message.answer("Это для учителей.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[screen_button(cfg, "👩‍🏫 Открыть учеников", "teacher")]])
    if not rows:
        await message.answer("Тетрадь пока никто не делал.", reply_markup=keyboard)
        return
    lines = [
        f"• {r['name']} — сделано {r['done']}, с первого раза {r['first_try']}"
        + (f", ❗ ошибок: {r['mistakes']}" if r["mistakes"] else "")
        for r in rows[:30]
    ]
    await message.answer("Ученики тетради:\n\n" + "\n".join(lines), reply_markup=keyboard)
