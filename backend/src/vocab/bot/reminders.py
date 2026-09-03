"""Напоминания. APScheduler живёт в процессе бота: он и так держит event loop
и умеет отправлять сообщения, а отдельный шедулер-сервис пришлось бы учить
работать с Telegram заново."""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..client import VocabAPI
from ..config import Settings
from .handlers import review_keyboard

log = logging.getLogger(__name__)


async def notify_due(bot: Bot, api: VocabAPI, cfg: Settings) -> None:
    for user in await api.due_users():
        try:
            await bot.send_message(
                user["tg_id"],
                f"На повторение: {user['due']}",
                reply_markup=review_keyboard(cfg),
            )
        except Exception as exc:  # noqa: BLE001
            # Один заблокировавший бота пользователь не должен обрывать
            # рассылку остальным, но и молча пропасть ошибка не должна.
            log.warning("не отправил напоминание %s: %s", user["tg_id"], exc)


def start_scheduler(bot: Bot, api: VocabAPI, cfg: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=cfg.tz)
    for hour in cfg.reminder_hour_list:
        scheduler.add_job(
            notify_due,
            CronTrigger(hour=hour, minute=0),
            args=(bot, api, cfg),
            id=f"remind-{hour}",
            # Контейнер, перезапущенный в 09:03, не должен присылать
            # пропущенное напоминание — оно уже неактуально.
            misfire_grace_time=300,
        )
    scheduler.start()
    log.info("напоминания в %s (%s)", cfg.reminder_hour_list, cfg.tz)
    return scheduler
