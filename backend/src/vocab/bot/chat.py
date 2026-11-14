"""Чат как приложение: виджеты карточки, разминки, теста, глаголов и табло,
и ответы на их запросы. Запрос виджета — строка до 64 байт «вид:аргументы»,
ответ — JSON до 1 КБ."""

import logging
import random
from dataclasses import dataclass
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from ..client import VocabAPI
from ..config import Settings
from .widget import MAX_DATA, Query, Widgets, dump

log = logging.getLogger(__name__)

WARMUP_SIZE = 5
QUIZ_SIZE = 10
# Слово длиннее не собрать плитками на экране 320 px.
SPELL_MAX = 10
# Оценки FSRS: выбор из вариантов за верный ответ — только Hard.
AGAIN, HARD, GOOD = 1, 2, 3


def cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def fit(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Укорачивает список data[key] с конца, пока данные не влезут в 1 КБ."""
    while len(dump(data).encode()) > MAX_DATA and data[key]:
        data[key].pop()
    return data


def title(card: dict[str, Any]) -> str:
    return f"to {card['word']}" if card.get("homonym") and card["pos"] == "verb" else card["word"]


def app_button(cfg: Settings, text: str, screen: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=f"{cfg.miniapp_url}?screen={screen}"))


def app_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    """Два раздела мини-аппа: тетрадь по грамматике и слова."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        app_button(cfg, "📒 Тетрадь", "grammar"), app_button(cfg, "🧠 Приложение", "cards"),
    ]])


def learn_keyboard(cfg: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[app_button(cfg, "🎓 Тренировка", "learn")]])


# --- карточка слова ----------------------------------------------------------


def card_data(entry: dict[str, Any]) -> dict[str, Any]:
    return fit({
        "w": entry["lemma"], "i": entry["ipa"], "p": entry["pos"], "x": entry["irregular"],
        "f": entry["forms"], "n": entry["form_note"] or "", "t": cut(entry["translation"], 120),
        "r": entry["top"], "l": entry["learners"], "c": entry["created"],
        "e": [[cut(e["en"], 140), cut(e["ru"], 140)] for e in entry["examples"][:3]],
    }, "e")


def contrast_lines(contrast: dict[str, Any] | None) -> list[str]:
    """«⚖️ Не путай: carry — нести в руках» и частые сочетания."""
    if not contrast:
        return []
    lines = []
    if contrast["others"]:
        lines += ["", "⚖️ Не путай:"] + [f"{o['word']} — {o['note']}" for o in contrast["others"]]
    if contrast["collocations"]:
        lines += ["", "🔗 " + " · ".join(contrast["collocations"])]
    return lines


def card_text(entry: dict[str, Any]) -> str:
    """Карточка обычным сообщением — когда виджеты запрещены."""
    head = " · ".join(filter(None, [f"/{entry['ipa']}/" if entry["ipa"] else "", entry["pos"],
                                     "неправильное" if entry["irregular"] else ""]))
    lines = [entry["lemma"], head]
    if entry["form_note"]:
        lines.append(f"🔤 {entry['form_note']}")
    if entry["forms"]:
        lines.append(entry["forms"])
    lines += ["", f"👉 {entry['translation']}", ""]
    lines += [f"• {e['en']}\n  {e['ru']}" for e in entry["examples"][:3]]
    lines += contrast_lines(entry["contrast"])
    added = "✅ добавлено" if entry["created"] else "уже было у тебя"
    lines += ["", f"⭐ {entry['top']} · учат: {entry['learners']} · {added}"]
    return "\n".join(lines)


# --- разминка ------------------------------------------------------------------


async def send_warmup(widgets: Widgets, api: VocabAPI, cfg: Settings, tg_id: int) -> bool:
    """Пять слов, которые пора повторить. False — повторять нечего."""
    cards = (await api.queue(tg_id))[:WARMUP_SIZE]
    if not cards:
        return False
    data = fit({"c": [
        [c["id"], title(c), cut(c["translation"], 60), cut(c["examples"][0]["en"], 100) if c["examples"] else ""]
        for c in cards
    ]}, "c")
    words = ", ".join(c[1] for c in data["c"])
    fallback = (f"⚡ Разминка: пора повторить {words}", learn_keyboard(cfg))
    await widgets.replace(tg_id, "warmup", data, queries=True, fallback=fallback)
    return True


async def on_rate(query: Query, ctx: dict[str, Any]) -> None:
    """r:<card_id>:<rating> — оценка из разминки."""
    _, card_id, rating = query["data"].split(":")
    if rating not in ("1", "3"):
        raise ValueError(f"разминка шлёт только 1 или 3: {query['data']!r}")
    await ctx["api"].review(query["from"]["id"], int(card_id), int(rating), "warmup")
    await ctx["widgets"].answer(query, {"ok": 1})


# --- тест ----------------------------------------------------------------------


@dataclass
class Quiz:
    cards: list[dict[str, Any]]
    index: int = 0
    right: int = 0


# В памяти процесса: перезапуск теряет только недоотвеченный вопрос,
# оценки отвеченных уже в API.
quizzes: dict[int, Quiz] = {}


def question(quiz: Quiz) -> dict[str, Any]:
    if quiz.index >= len(quiz.cards):
        return {"end": [quiz.right, len(quiz.cards)]}
    card = quiz.cards[quiz.index]
    head = {"id": card["id"], "n": [quiz.index + 1, len(quiz.cards)]}
    word = card["word"]
    # Через вопрос — собрать слово из букв: вспомнить, а не узнать.
    if quiz.index % 2 and len(word) <= SPELL_MAX and word.replace(" ", "").isalpha():
        return {**head, "k": "s", "q": cut(card["translation"], 80), "a": word}
    options = [cut(o, 60) for o in card["choices_ru"]]
    return {**head, "k": "c", "q": title(card), "o": options, "a": card["choices_ru"].index(card["translation"])}


async def send_quiz(widgets: Widgets, api: VocabAPI, cfg: Settings, tg_id: int) -> bool:
    cards = [c for c in await api.quiz(tg_id, QUIZ_SIZE) if len(c["choices_ru"]) >= 2]
    if not cards:
        return False
    quizzes[tg_id] = Quiz(cards)
    fallback = ("🎯 Тест — в приложении: тренировка ведёт каждое слово в разные стороны.", learn_keyboard(cfg))
    await widgets.replace(tg_id, "quiz", queries=True, fallback=fallback)
    return True


async def on_quiz(query: Query, ctx: dict[str, Any]) -> None:
    """q — первый вопрос; a:<card_id>:<rating> — ответ и следующий вопрос."""
    tg_id = query["from"]["id"]
    quiz = quizzes.get(tg_id)
    if quiz is None:
        await ctx["widgets"].answer(query, {"end": None})
        return
    if query["data"].startswith("a:"):
        _, card_id, rating = query["data"].split(":")
        if int(card_id) != quiz.cards[quiz.index]["id"] or rating not in ("1", "2", "3"):
            raise ValueError(f"ответ не на текущий вопрос: {query['data']!r}")
        await ctx["api"].review(tg_id, int(card_id), int(rating), "chat-quiz")
        quiz.right += rating != "1"
        quiz.index += 1
    answer = question(quiz)
    if "end" in answer:
        del quizzes[tg_id]
    await ctx["widgets"].answer(query, answer)


# --- глаголы на скорость -------------------------------------------------------


def first_forms(forms: str) -> list[str]:
    """«get · got · got/gotten» → [get, got, got]."""
    return [f.split("/")[0].strip() for f in forms.split("·")]


async def send_verbs(widgets: Widgets, api: VocabAPI, cfg: Settings, tg_id: int) -> bool:
    game = await api.verbs(tg_id)
    verbs = [first_forms(v["forms"]) for v in game["verbs"]]
    verbs = [v for v in verbs if len(v) == 3]
    if not verbs:
        return False
    random.shuffle(verbs)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[app_button(cfg, "⚡ Неправильные глаголы", "irregular")]])
    fallback = (f"🔁 Неправильные глаголы — в приложении. Рекорд: {game['best']}", keyboard)
    await widgets.replace(tg_id, "verbs", fit({"v": verbs, "b": game["best"]}, "v"), queries=True, fallback=fallback)
    return True


async def on_verbs(query: Query, ctx: dict[str, Any]) -> None:
    """v:<score> — конец раунда, в ответ рекорд."""
    score = int(query["data"].split(":")[1])
    best = await ctx["api"].verbs_score(query["from"]["id"], score)
    await ctx["widgets"].answer(query, {"b": best})


# --- табло ---------------------------------------------------------------------


def board_text(s: dict[str, Any]) -> str:
    return (f"📊 Мои слова\n\n🔥 Серия {s['streak']} (рекорд {s['best_streak']})\n"
            f"⏰ Ждут повторения: {s['due_now']}\n✅ Выучено: {s['learned']}/{s['total']}\n"
            f"🆕 Новых сегодня: {s['new_left']}\n\nПришли английское слово — покажу карточку и добавлю в повторение.")


async def send_board(widgets: Widgets, api: VocabAPI, cfg: Settings, tg_id: int) -> None:
    """Главная страница чата: цифры и кнопки. Закреплена, старая удаляется."""
    keyboard = app_keyboard(cfg)
    fallback = (board_text(await api.stats(tg_id)),
                InlineKeyboardMarkup(inline_keyboard=[*keyboard.inline_keyboard, *learn_keyboard(cfg).inline_keyboard]))
    message_id = await widgets.replace(tg_id, "board", queries=True, keyboard=keyboard, fallback=fallback)
    await widgets.call("pinChatMessage", chat_id=tg_id, message_id=message_id, disable_notification=True)


async def on_stats(query: Query, ctx: dict[str, Any]) -> None:
    """s — свежие цифры: табло спрашивает их само, когда появляется на экране."""
    s = await ctx["api"].stats(query["from"]["id"])
    await ctx["widgets"].answer(query, {
        "s": s["streak"], "b": s["best_streak"], "d": s["due_now"],
        "l": s["learned"], "t": s["total"], "n": s["new_left"],
    })


OPENERS = {"warmup": send_warmup, "quiz": send_quiz, "verbs": send_verbs}
EMPTY = {
    "warmup": "Повторять пока нечего — всё вовремя 👌",
    "quiz": "Тестировать пока нечего: сначала пройди новые слова.",
    "verbs": "Глаголов в словаре пока нет.",
}


async def on_open(query: Query, ctx: dict[str, Any]) -> None:
    """go:<вид> — кнопка табло открывает разминку, тест или игру."""
    kind = query["data"].split(":")[1]
    sent = await OPENERS[kind](ctx["widgets"], ctx["api"], ctx["cfg"], query["from"]["id"])
    await ctx["widgets"].answer(query, {"ok": 1} if sent else {"msg": EMPTY[kind]})


HANDLERS = {"r": on_rate, "q": on_quiz, "a": on_quiz, "v": on_verbs, "s": on_stats, "go": on_open}
