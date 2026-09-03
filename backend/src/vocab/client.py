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
            timeout=httpx.Timeout(10.0),
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

    async def add_word(
        self, tg_id: int, word: str, source_url: str | None = None
    ) -> dict[str, Any]:
        return await self._call(
            "POST", "/words", tg_id, json={"word": word, "source_url": source_url}
        )

    async def retry(self, tg_id: int, card_id: int) -> dict[str, Any]:
        return await self._call("POST", f"/words/{card_id}/retry", tg_id)

    async def stats(self, tg_id: int) -> dict[str, Any]:
        return await self._call("GET", "/stats", tg_id)

    async def failed(self, tg_id: int) -> list[dict[str, Any]]:
        return await self._call("GET", "/words/failed", tg_id)

    async def search(self, tg_id: int, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return await self._call(
            "GET", "/words/search", tg_id, params={"q": query, "limit": limit}
        )

    async def weak(self, tg_id: int, limit: int = 20) -> list[dict[str, Any]]:
        return await self._call("GET", "/words/weak", tg_id, params={"limit": limit})

    async def due_users(self) -> list[dict[str, Any]]:
        return await self._call("GET", "/internal/due")
