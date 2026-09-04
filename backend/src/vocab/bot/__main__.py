"""Точка входа бота: python -m vocab.bot"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonWebApp, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..client import VocabAPI
from ..config import settings
from .handlers import router
from .middleware import OwnerOnly
from .reminders import start_scheduler

log = logging.getLogger(__name__)


async def main() -> None:
    cfg = settings()
    logging.basicConfig(
        level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=None))
    api = VocabAPI(cfg)

    dispatcher = Dispatcher()
    dispatcher.message.middleware(OwnerOnly(cfg.owner_tg_id))
    dispatcher.callback_query.middleware(OwnerOnly(cfg.owner_tg_id))
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
                text="Повторять", web_app=WebAppInfo(url=cfg.miniapp_url)
            )
        )
        scheduler = start_scheduler(bot, api, cfg)
        await dispatcher.start_polling(bot, api=api, cfg=cfg)
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await api.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
