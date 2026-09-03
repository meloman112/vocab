"""Фильтр владельца."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

log = logging.getLogger(__name__)


class OwnerOnly(BaseMiddleware):
    """Пускает только владельца словаря.

    Токен бота однажды утечёт в чей-нибудь скриншот, а ссылку на бота найдут
    поиском. Без этого фильтра любой желающий наполнял бы базу и жёг квоту
    DeepSeek. Мультиюзер появится вместе с регистрацией, а не так.
    """

    def __init__(self, owner_tg_id: int) -> None:
        self.owner_tg_id = owner_tg_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.id != self.owner_tg_id:
            log.warning("отклонён чужой пользователь %s", user.id if user else "?")
            return None
        return await handler(event, data)
