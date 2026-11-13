"""Хендлеры бота. Логики нет: всё через API, бот — просто ещё один клиент."""

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PollAnswer,
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
                text="🧠 Повторять", web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen=cards")
            )
        ]]
    )


def start_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    """Два раздела одного бота: тетрадь по грамматике и слова."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="📒 Тетрадь", web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen=grammar")),
            InlineKeyboardButton(text="🧠 Слова", web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen=cards")),
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


async def send_entries(message: Message, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        await message.answer(format_entry(entry), reply_markup=entry_keyboard(entry))


def _callback(text: str, data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text[:60], callback_data=data)]


async def add_and_reply(
    message: Message, tg_id: int, api: VocabAPI, text: str,
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
            await message.answer(detail)
            return
        rows = [_callback(f"➕ {detail['suggestion']}", f"add:{detail['suggestion']}")]
        if len(f"asis:{text}".encode()) <= MAX_CALLBACK:
            rows.append(_callback(f"Нет, именно «{text}»", f"asis:{text}"))
        await message.answer(detail["message"], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        return
    await send_entries(message, entries)


@router.message(Command("start"))
async def start(message: Message, cfg: Settings) -> None:
    await message.answer(
        "Привет! Здесь два раздела.\n\n"
        "📒 Тетрадь — 134 упражнения по грамматике из Work book: времена, Passive, "
        "Conditionals, Relative clauses, Gerund, модальные глаголы, Participle. "
        "Каждую ошибку бот разбирает, а учитель видит, где ты споткнулся.\n\n"
        "🧠 Слова — пришли английское слово в любой форме (went, children, reading): "
        "отвечу переводом, формой и примерами и добавлю в повторение. "
        "Части речи уточняй так: to book (бронировать), a book (книга). "
        "Из фразы или предложения достану устойчивые выражения.\n\n"
        "/grammar — тетрадь\n/review — повторение слов и тесты\n/quiz — тест прямо в чате\n"
        "/stats — цифры и серия\n/top — что учат чаще всего\n/rating — рейтинг недели",
        reply_markup=start_keyboard(cfg),
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


@router.message(Command("quiz"))
async def quiz(message: Message, api: VocabAPI, cfg: Settings) -> None:
    """Тест в самом чате: quiz-опросы Telegram, ответ сразу идёт в FSRS."""
    cards = await api.quiz(message.from_user.id, QUIZ_SIZE)
    cards = [c for c in cards if len(c["choices_ru"]) >= 2]
    if not cards:
        await message.answer(
            "Тестировать пока нечего: сначала пройди новые слова карточками.",
            reply_markup=review_keyboard(cfg),
        )
        return
    # Опросы прошлого теста забываются: ответ на них сдвинул бы счёт нового.
    for poll_id in [p for p, asked in polls.items() if asked[0] == message.from_user.id]:
        del polls[poll_id]
    quizzes[message.from_user.id] = Quiz(message.chat.id, cards)
    await send_question(message.bot, message.from_user.id)


@router.poll_answer()
async def quiz_answer(answer: PollAnswer, bot: Bot, api: VocabAPI) -> None:
    asked = polls.pop(answer.poll_id, None)
    # Опрос из прошлого запуска бота: его карточка уже неизвестна.
    if asked is None:
        return
    tg_id, card_id, correct = asked
    right = answer.option_ids == [correct]
    await api.review(tg_id, card_id, RIGHT if right else WRONG, "poll")
    session = quizzes.get(tg_id)
    if session is None:
        return
    session.right += right
    session.index += 1
    await send_question(bot, tg_id)


# Сколько вопросов в одном /quiz и какие оценки FSRS ставит ответ. Верно
# здесь — Hard, а не Good: опрос — выбор из вариантов, узнать не значит вспомнить.
QUIZ_SIZE = 10
RIGHT, WRONG = 2, 1
# Лимиты Telegram на опрос.
POLL_QUESTION, POLL_OPTION, POLL_EXPLANATION = 300, 100, 200


@dataclass
class Quiz:
    chat_id: int
    cards: list[dict[str, Any]]
    index: int = 0
    right: int = 0


# Состояние тестов в памяти процесса: перезапуск бота теряет только
# недоотвеченный опрос, а оценки уже отвеченных лежат в API.
quizzes: dict[int, Quiz] = {}
# poll_id → (tg_id, card_id, номер правильного варианта).
polls: dict[str, tuple[int, int, int]] = {}


async def send_question(bot: Bot, tg_id: int) -> None:
    session = quizzes[tg_id]
    if session.index >= len(session.cards):
        del quizzes[tg_id]
        await bot.send_message(
            session.chat_id,
            f"Готово: {session.right} из {len(session.cards)}. /quiz — ещё",
        )
        return
    card = session.cards[session.index]
    title = f"to {card['word']}" if card["homonym"] and card["pos"] == "verb" else card["word"]
    options = [option[:POLL_OPTION] for option in card["choices_ru"]]
    # Примеры админ может стереть в редакторе слова — тогда без пояснения.
    example = card["examples"][0] if card["examples"] else None
    correct = card["choices_ru"].index(card["translation"])
    sent = await bot.send_poll(
        session.chat_id,
        question=f"{session.index + 1}/{len(session.cards)}. {title} — как переводится?"[:POLL_QUESTION],
        options=options,
        type="quiz",
        correct_option_id=correct,
        is_anonymous=False,
        explanation=f"{example['en']} — {example['ru']}"[:POLL_EXPLANATION] if example else None,
    )
    polls[sent.poll.id] = (tg_id, card["id"], correct)


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
    await add_and_reply(message, message.from_user.id, api, text)


@router.callback_query(F.data.startswith("sense:"))
async def add_sense(callback: CallbackQuery, api: VocabAPI) -> None:
    """Кнопка «➕ to book»: то же добавление, но с выбранной частью речи."""
    _, pos, lemma = callback.data.split(":", 2)
    # Отвечаем сразу: новое значение ждёт ИИ дольше, чем Telegram ждёт ответа
    # на нажатие, и у пользователя повисли бы часики на кнопке.
    await callback.answer()
    await add_and_reply(callback.message, callback.from_user.id, api, lemma, pos)


@router.callback_query(F.data.startswith("add:"))
async def add_suggestion(callback: CallbackQuery, api: VocabAPI) -> None:
    """«➕ help» под «Слова helf нет. Может, help?»."""
    await callback.answer()
    await add_and_reply(callback.message, callback.from_user.id, api, callback.data[4:])


@router.callback_query(F.data.startswith("asis:"))
async def add_as_is(callback: CallbackQuery, api: VocabAPI) -> None:
    await callback.answer()
    await add_and_reply(callback.message, callback.from_user.id, api, callback.data[5:], as_is=True)


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
