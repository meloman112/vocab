"""MCP-сервер: доступ к словарю из LibreChat и Claude.

Смонтирован в то же приложение FastAPI, отдельным контейнером не поднимается:
процесс, который умеет только четыре тула, не стоит своего compose-сервиса.
"""

import hmac
import logging

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from ..client import VocabAPI
from ..config import Settings

log = logging.getLogger(__name__)


class BearerGuard:
    """Пускает к /mcp только с Authorization: Bearer <API_TOKEN>.

    Свой guard вместо StaticTokenVerifier из fastmcp: тот держит токены
    в словаре открытым текстом и сам помечен как непригодный для прода,
    а нам нужно ровно одно сравнение — зато постоянного времени.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        header = dict(scope["headers"]).get(b"authorization", b"")
        expected = b"Bearer " + self.token
        if not hmac.compare_digest(header, expected):
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            })
            await send({"type": "http.response.body", "body": "unauthorized".encode()})
            return

        await self.app(scope, receive, send)


def build_mcp_app(cfg: Settings):
    """Собирает ASGI-приложение MCP. Тулы работают от владельца словаря:
    транспорт MCP не несёт пользователя, а словарь пока один."""
    mcp = FastMCP("vocab")
    api = VocabAPI(cfg)
    tg_id = cfg.owner_tg_id

    @mcp.tool
    async def add_word(word: str, context: str | None = None) -> dict:
        """Добавить английское слово в словарь. context — где оно встретилось."""
        return await api.add_word(tg_id, word, context)

    @mcp.tool
    async def due_count() -> dict:
        """Сколько карточек ждёт повторения прямо сейчас и сегодня."""
        stats = await api.stats(tg_id)
        return {"due_now": stats["due_now"], "due_today": stats["due_today"]}

    @mcp.tool
    async def search_words(query: str, limit: int = 20) -> list[dict]:
        """Найти карточки по части слова."""
        return await api.search(tg_id, query, limit)

    @mcp.tool
    async def weak_cards(limit: int = 20) -> list[dict]:
        """Карточки с наибольшим числом провалов — на чём чаще всего сыплюсь."""
        return await api.weak(tg_id, limit)

    return mcp.http_app(
        path="/",
        middleware=[Middleware(BearerGuard, token=cfg.api_token)],
        # fastmcp сверяет заголовок Host и незнакомый отвергает; за Caddy
        # в Host приезжает внешний домен, а не имя контейнера.
        allowed_hosts=[cfg.domain] if cfg.domain else None,
        # Состояние сессии здесь не нужно: тулы не имеют памяти между вызовами,
        # а stateless-режим переживает перезапуск контейнера без ошибок у клиента.
        stateless_http=True,
    )
