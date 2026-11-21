"""Напоминания. APScheduler живёт в процессе бота: он и так держит event loop
и умеет отправлять сообщения, а отдельный шедулер-сервис пришлось бы учить
работать с Telegram заново."""

import html
import logging
import re
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..client import VocabAPI
from ..config import Settings
from . import chat
from .handlers import review_keyboard
from .widget import Widgets
from .exams import post_summaries
from .teachers import test_keyboard

log = logging.getLogger(__name__)


# Сколько дней молчания → что сказать. Дни выбраны как у Duolingo:
# сразу после потери серии, через пару дней, через неделю и последнее.
# После 14 дней — тишина: дальше напоминания уже только раздражают.
COMEBACK_TEXTS = {
    2: "Серия прервалась 😢 Начни новую — хватит пяти минут.",
    3: "Три дня без повторений — слова начинают забываться. Вернёмся?",
    7: "Неделю не виделись. Слова ждут, а память — нет 🧠",
    14: "Последнее напоминание: словарь на месте, возвращайся, когда захочешь.",
}


def reminder_text(target: dict[str, Any], evening: bool) -> str | None:
    """Что написать пользователю, который сегодня ещё не занимался. None — молчать.

    Утром и днём — мягко, вечером — только если горит серия: напоминать
    вечером о давно брошенном словаре значит писать дважды в день впустую.
    """
    gap, due, streak = target["gap"], target["due"], target["streak"]
    if gap is None:
        if evening or not due:
            return None
        return f"{due} слов ждут первого повторения 🧠"
    if gap == 1:
        if evening:
            return f"🔥 Серия {streak} дн. сгорит в полночь! Одно повторение её спасёт."
        todo = f"{due} слов ждут." if due else "возьми новые слова."
        return f"🔥 Серия {streak} дн. Сегодня ещё не занимался — {todo}"
    if evening:
        return None
    return COMEBACK_TEXTS.get(gap)


async def notify(bot: Bot, api: VocabAPI, cfg: Settings) -> None:
    for target in await api.reminder_targets():
        text = reminder_text(target, target["evening"])
        if text is None:
            continue
        try:
            await bot.send_message(target["tg_id"], text, reply_markup=review_keyboard(cfg))
        except Exception as exc:  # noqa: BLE001
            # Один заблокировавший бота пользователь не должен обрывать
            # рассылку остальным, но и молча пропасть ошибка не должна.
            log.warning("не отправил напоминание %s: %s", target["tg_id"], exc)


async def remind_tests(bot: Bot, api: VocabAPI, cfg: Settings) -> None:
    """Тест со сроком завтра ещё не сдан — одно напоминание."""
    for target in await api.test_reminders():
        try:
            await bot.send_message(
                target["tg_id"], f"⏰ Завтра последний день сдать тест «{target['title']}».",
                reply_markup=test_keyboard(cfg, target["test_id"]),
            )
        except Exception as exc:  # noqa: BLE001 — как в notify: остальным напоминание дойти должно
            log.warning("не напомнил о тесте %s: %s", target["tg_id"], exc)


async def warmups(widgets: Widgets, api: VocabAPI, cfg: Settings) -> None:
    """Разминка всем, у кого есть слова к повторению: прежняя из чата уходит."""
    for target in await api.warmup_targets():
        try:
            await chat.send_warmup(widgets, api, cfg, target["tg_id"])
        except Exception as exc:  # noqa: BLE001 — как в notify: остальным разминка дойти должна
            log.warning("не отправил разминку %s: %s", target["tg_id"], exc)


def item_label(item: str) -> str:
    """«23-3» — упражнение 23, индекс с нуля, а учитель считает с единицы."""
    exercise, index = item.split("-")
    return f"упр. {exercise} №{int(index) + 1}"


def digest_text(digest: dict[str, Any]) -> str | None:
    """Сводка тетради за неделю простым текстом: имена приходят от
    пользователей, а без parse_mode их не нужно экранировать. None — молчать."""
    students = digest["students"]
    if not students:
        return None
    lines = ["📊 Тетрадь за неделю", f"Занимались: {len(students)}", ""]
    for s in students:
        line = f"{s['name']} — {s['done']} заданий, с первого раза {round(100 * s['first_try'] / s['done'])}%"
        if s["top_mistake"]:
            line += f". Чаще всего: {s['top_mistake']} ({s['top_count']})"
        lines.append(line)
    if digest["hard_items"]:
        lines += ["", "Ошиблись несколько учеников:"]
        lines += [f"• {item_label(i['item'])} — {i['students']} уч." for i in digest["hard_items"]]
    return "\n".join(lines)


async def send_digest(bot: Bot, api: VocabAPI, cfg: Settings) -> None:
    markup = InlineKeyboardMarkup(inline_keyboard=[[chat.app_button(cfg, "👥 Ученики", "teacher")]])
    for digest in await api.digest():
        text = digest_text(digest)
        if text is None:
            continue
        for tg_id in digest["teachers"]:
            try:
                await bot.send_message(tg_id, text, reply_markup=markup)
            except Exception as exc:  # noqa: BLE001 — как в notify: остальным учителям сводка дойти должна
                log.warning("не отправил сводку %s: %s", tg_id, exc)


def word_of_day_text(w: dict[str, Any]) -> str:
    """Слово жирным и в самом предложении: видно, где оно встретилось."""
    sentence = re.sub(rf"\b({re.escape(w['lemma'])})\b", r"<b>\1</b>", html.escape(w["en"]), flags=re.I)
    ipa = f" [{html.escape(w['ipa'])}]" if w["ipa"] else ""
    return (f"📖 Слово дня: <b>{html.escape(w['lemma'])}</b>{ipa} — {html.escape(w['translation'])}\n\n"
            f"Из твоей тетради, упражнение {w['exercise']}:\n<i>{sentence}</i>\n{html.escape(w['ru'])}")


def word_of_day_keyboard(lemma: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ В мои слова", callback_data=f"add:{lemma}"),
        InlineKeyboardButton(text="🔕 Не присылать", callback_data="wod:off"),
    ]])


async def send_word_of_day(bot: Bot, api: VocabAPI) -> None:
    for w in await api.word_of_day():
        try:
            await bot.send_message(w["tg_id"], word_of_day_text(w), parse_mode="HTML",
                                   reply_markup=word_of_day_keyboard(w["lemma"]))
        except Exception as exc:  # noqa: BLE001 — как в notify: остальным слово дойти должно
            log.warning("не отправил слово дня %s: %s", w["tg_id"], exc)


async def keep_warm(bot: Bot, widgets: Widgets) -> None:
    """Пинг Telegram, чтобы соединения не простаивали: Telegram держит
    простаивающее соединение 3–7 минут, а новое с test_moe — до 3 с,
    и их ждал бы первый тап в виджете после паузы."""
    await bot.get_me()
    await widgets.call("getMe")


def start_scheduler(bot: Bot, api: VocabAPI, cfg: Settings, widgets: Widgets) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=cfg.tz)
    # Напоминания и разминки — каждый час: чей сейчас местный час из
    # REMINDER_HOURS и WARMUP_HOURS, решает API по поясу пользователя.
    # Контейнер, перезапущенный в 09:03, не должен присылать пропущенное
    # напоминание — оно уже неактуально.
    scheduler.add_job(notify, CronTrigger(minute=0), args=(bot, api, cfg),
                      id="remind", misfire_grace_time=300)
    scheduler.add_job(warmups, CronTrigger(minute=0), args=(widgets, api, cfg),
                      id="warmup", misfire_grace_time=300)
    # Срок теста общий для класса, поэтому о нём — по общему поясу.
    scheduler.add_job(remind_tests, CronTrigger(hour=max(cfg.reminder_hour_list), minute=5),
                      args=(bot, api, cfg), id="remind-tests", misfire_grace_time=300)
    scheduler.add_job(send_digest, CronTrigger(day_of_week=cfg.digest_days, hour=cfg.digest_hour, minute=0),
                      args=(bot, api, cfg), id="digest", misfire_grace_time=300)
    scheduler.add_job(send_word_of_day, CronTrigger(minute=0), args=(bot, api),
                      id="word-of-day", misfire_grace_time=300)
    scheduler.add_job(post_summaries, IntervalTrigger(seconds=30), args=(bot, api), id="exam-summaries")
    scheduler.add_job(keep_warm, IntervalTrigger(minutes=3), args=(bot, widgets), id="keep-warm")
    scheduler.start()
    log.info("напоминания в %s, разминки в %s по местному времени, без пояса — %s",
             cfg.reminder_hour_list, cfg.warmup_hour_list, cfg.tz)
    return scheduler
