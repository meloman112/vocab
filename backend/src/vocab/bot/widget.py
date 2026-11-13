"""HTML-виджеты в сообщениях (Bot API 10.4). aiogram 3.31 их ещё не знает,
поэтому методы зовутся напрямую, а widget_query перехватывается до того,
как aiogram отбросит незнакомое обновление.

HTML отправленного виджета не меняется, меняются только данные (chat_data),
поэтому каждый виджет — шаблон, а содержимое приходит в данных или
ответом бота на запрос из виджета.
"""

import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from functools import cache
from pathlib import Path
from typing import Any

import httpx
from aiogram.types import InlineKeyboardMarkup

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent / "widgets"
# Лимиты Bot API: данные сообщения и ответ на запрос — до 1 КБ.
MAX_DATA = 1024

Query = dict[str, Any]
Handler = Callable[[Query, dict[str, Any]], Awaitable[Any]]


class TelegramError(Exception):
    """Bot API ответил ok: false."""


@cache
def template(name: str) -> str:
    """Шаблон с общими стилями и помощниками из _base.html."""
    return (TEMPLATES / "_base.html").read_text() + (TEMPLATES / f"{name}.html").read_text()


def dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def pack(data: Any) -> str:
    text = dump(data)
    if len(text.encode()) > MAX_DATA:
        raise ValueError(f"данные виджета больше {MAX_DATA} байт: {text[:80]}…")
    return text


class Widgets:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(base_url=f"https://api.telegram.org/bot{token}/", timeout=30)
        # chat_id → вид виджета → его сообщения. Старые удаляются, когда приходит
        # новое того же вида: в чате остаётся одна разминка, один тест, одна
        # карточка. Память процесса: после перезапуска старые просто останутся.
        self.messages: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    async def close(self) -> None:
        await self._client.aclose()

    async def call(self, method: str, **params: Any) -> Any:
        response = await self._client.post(method, json={k: v for k, v in params.items() if v is not None})
        body = response.json()
        if not body.get("ok"):
            raise TelegramError(f"{method}: {body.get('description')}")
        return body["result"]

    async def replace(self, chat_id: int, name: str, data: Any = None, **kwargs: Any) -> int:
        """Новый виджет name вместо прежних того же вида."""
        await self.clean(chat_id, name)
        return await self.send(chat_id, name, data, **kwargs)

    async def send(
        self, chat_id: int, name: str, data: Any = None, *, queries: bool = False,
        keyboard: InlineKeyboardMarkup | None = None,
    ) -> int:
        """Шлёт виджет name и запоминает его для чистки. Возвращает message_id."""
        message = await self.call(
            "sendWidget", chat_id=chat_id, html=template(name),
            chat_data=None if data is None else pack(data), allow_queries=queries or None,
            reply_markup=keyboard.model_dump(exclude_none=True) if keyboard else None,
        )
        self.track(chat_id, name, message["message_id"])
        return message["message_id"]

    def track(self, chat_id: int, kind: str, message_id: int) -> None:
        self.messages[chat_id][kind].append(message_id)

    async def clean(self, chat_id: int, kind: str) -> None:
        ids = self.messages[chat_id].pop(kind, [])
        if not ids:
            return
        try:
            await self.call("deleteMessages", chat_id=chat_id, message_ids=ids)
        except TelegramError as exc:
            # Старше 48 часов Telegram удалить не даст — сообщения просто останутся.
            log.warning("не удалил %s в %s: %s", ids, chat_id, exc)

    async def answer(self, query: Query, data: Any) -> None:
        await self.call("answerWidgetQuery", widget_query_id=query["id"], data=pack(data))


def middleware(handlers: dict[str, Handler]):
    """Outer-middleware апдейтов: widget_query уходит в handlers по префиксу
    data до двоеточия, всё остальное — дальше в aiogram."""

    async def outer(handler, update, data):
        query = (update.model_extra or {}).get("widget_query")
        if query is None:
            return await handler(update, data)
        kind = query["data"].split(":", 1)[0]
        if kind not in handlers:
            raise ValueError(f"неизвестный запрос виджета: {query['data']!r}")
        return await handlers[kind](query, data)

    return outer
