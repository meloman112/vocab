"""HTTP-клиент к собственному API. Им пользуются бот и MCP-сервер.

Ни тот, ни другой не ходят в базу напрямую: тогда схему знали бы три
процесса, а обогащение пришлось бы запускать в каждом заново.
"""

from typing import Any

import httpx

from .config import Settings


class VocabAPI:
    def __init__(self, cfg: Settings) -> None:
        self._client = httpx.AsyncClient(
            base_url=cfg.api_base_url,
            headers={"X-Token": cfg.api_token},
            # Новое слово ждёт ответа ИИ: до двух попыток по 20 секунд, а для
            # фразы ещё и поиск фраз перед ними.
            timeout=httpx.Timeout(90.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(
        self, method: str, url: str, tg_id: int | None = None, **kwargs: Any
    ) -> Any:
        headers = {"X-Tg-Id": str(tg_id)} if tg_id is not None else None
        response = await self._client.request(method, url, headers=headers, **kwargs)
        # raise_for_status, а не молчаливый разбор: ошибку API должен увидеть
        # хендлер бота и сказать о ней пользователю, а не проглотить.
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    async def add_word(self, tg_id: int, word: str) -> list[dict[str, Any]]:
        body = await self._call("POST", "/words", tg_id, json={"word": word})
        return body["entries"]

    async def stats(self, tg_id: int) -> dict[str, Any]:
        return await self._call("GET", "/stats", tg_id)

    async def search(self, tg_id: int, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return await self._call(
            "GET", "/words/search", tg_id, params={"q": query, "limit": limit}
        )

    async def top(self, tg_id: int) -> list[dict[str, Any]]:
        return await self._call("GET", "/words/top", tg_id)

    async def weak(self, tg_id: int, limit: int = 20) -> list[dict[str, Any]]:
        return await self._call("GET", "/words/weak", tg_id, params={"limit": limit})

    async def leaderboard(self, tg_id: int) -> dict[str, Any]:
        return await self._call("GET", "/leaderboard", tg_id)

    async def reminder_targets(self) -> list[dict[str, Any]]:
        return await self._call("GET", "/internal/reminders")

    async def ban(self, word: str) -> None:
        await self._call("POST", "/internal/ban", json={"word": word})
