"""Напоминания. APScheduler живёт в процессе бота: он и так держит event loop
и умеет отправлять сообщения, а отдельный шедулер-сервис пришлось бы учить
работать с Telegram заново."""

import logging
from typing import Any

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..client import VocabAPI
from ..config import Settings
from . import chat
from .handlers import review_keyboard
from .widget import Widgets
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


async def notify(bot: Bot, api: VocabAPI, cfg: Settings, evening: bool) -> None:
    for target in await api.reminder_targets():
        text = reminder_text(target, evening)
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


async def warmups(widgets: Widgets, api: VocabAPI) -> None:
    """Разминка всем, у кого есть слова к повторению: прежняя из чата уходит."""
    for target in await api.warmup_targets():
        try:
            await chat.send_warmup(widgets, api, target["tg_id"])
        except Exception as exc:  # noqa: BLE001 — как в notify: остальным разминка дойти должна
            log.warning("не отправил разминку %s: %s", target["tg_id"], exc)


def start_scheduler(bot: Bot, api: VocabAPI, cfg: Settings, widgets: Widgets) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=cfg.tz)
    # Последнее напоминание дня — «вечернее»: в нём спасаем серию.
    evening_hour = max(cfg.reminder_hour_list)
    for hour in cfg.reminder_hour_list:
        scheduler.add_job(
            notify,
            CronTrigger(hour=hour, minute=0),
            args=(bot, api, cfg, hour == evening_hour),
            id=f"remind-{hour}",
            # Контейнер, перезапущенный в 09:03, не должен присылать
            # пропущенное напоминание — оно уже неактуально.
            misfire_grace_time=300,
        )
    scheduler.add_job(remind_tests, CronTrigger(hour=evening_hour, minute=5), args=(bot, api, cfg),
                      id="remind-tests", misfire_grace_time=300)
    for hour in cfg.warmup_hour_list:
        scheduler.add_job(warmups, CronTrigger(hour=hour, minute=0), args=(widgets, api),
                          id=f"warmup-{hour}", misfire_grace_time=300)
    scheduler.start()
    log.info("напоминания в %s, разминки в %s (%s)", cfg.reminder_hour_list, cfg.warmup_hour_list, cfg.tz)
    return scheduler
