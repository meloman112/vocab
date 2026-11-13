"""Точка входа бота: python -m vocab.bot"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..client import VocabAPI
from ..config import settings
from . import widget
from .chat import HANDLERS
from .handlers import router
from .reminders import start_scheduler
from .teachers import router as teachers_router

log = logging.getLogger(__name__)

# Подсказки в меню «/». Учительские и админские команды сюда не входят:
# ученику они ни к чему, а нужные люди о них знают.
COMMANDS = [
    BotCommand(command="grammar", description="📒 Тетрадь по грамматике"),
    BotCommand(command="review", description="🧠 Повторение слов и тесты"),
    BotCommand(command="stats", description="📊 Табло: цифры и кнопки"),
    BotCommand(command="warmup", description="⚡ Разминка: 5 слов в чате"),
    BotCommand(command="quiz", description="🎯 Тест по словам в чате"),
    BotCommand(command="verbs", description="🔁 Неправильные глаголы на скорость"),
    BotCommand(command="rating", description="Рейтинг недели"),
    BotCommand(command="top", description="Что учат чаще всего"),
]


async def main() -> None:
    cfg = settings()
    logging.basicConfig(
        level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    # httpx пишет каждый запрос с URL, а в URL Bot API — токен бота.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    bot = Bot(cfg.bot_token, session=widget.WarmSession(), default=DefaultBotProperties(parse_mode=None))
    api = VocabAPI(cfg)
    widgets = widget.Widgets(cfg.bot_token)

    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(widget.middleware(HANDLERS))
    # Тетрадь и учителя — раньше слов: основной роутер ловит любой текст.
    dispatcher.include_router(teachers_router)
    dispatcher.include_router(router)

    # Всё, что может упасть, — внутри try: иначе отказ Telegram на первом же
    # вызове оставлял бы открытыми сессии aiohttp, и логи тонули бы
    # в «Unclosed connector» вместо настоящей причины.
    scheduler: AsyncIOScheduler | None = None
    try:
        # Кнопка меню рядом с полем ввода — самый короткий путь до повторения,
        # без команды /review.
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Учиться", web_app=WebAppInfo(url=cfg.miniapp_url)
            )
        )
        await bot.set_my_commands(COMMANDS)
        scheduler = start_scheduler(bot, api, cfg, widgets)
        # widget_query aiogram сам не запросит: он его не знает.
        await dispatcher.start_polling(
            bot, api=api, cfg=cfg, widgets=widgets,
            allowed_updates=[*dispatcher.resolve_used_update_types(), "widget_query"],
        )
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await api.close()
        await widgets.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
