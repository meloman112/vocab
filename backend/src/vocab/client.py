"""HTTP-клиент к собственному API. Им пользуются бот и MCP-сервер.

Ни тот, ни другой не ходят в базу напрямую: тогда схему знали бы три
процесса, а обогащение пришлось бы запускать в каждом заново.
"""

from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings


class VocabAPI:
    def __init__(self, cfg: Settings) -> None:
        self._client = httpx.AsyncClient(
            base_url=cfg.api_base_url,
            headers={"X-Token": cfg.api_token},
            # Новое слово ждёт ответа ИИ: до двух попыток по 120 секунд, а для
            # фразы ещё и поиск фраз перед ними.
            timeout=httpx.Timeout(360.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(
        self, method: str, url: str, tg_id: int | None = None,
        tg_name: str | None = None, **kwargs: Any,
    ) -> Any:
        headers = {"X-Tg-Id": str(tg_id)} if tg_id is not None else {}
        if tg_name:
            # Заголовок HTTP — только latin-1, а имена бывают кириллицей.
            headers["X-Tg-Name"] = quote(tg_name)
        response = await self._client.request(method, url, headers=headers, **kwargs)
        # raise_for_status, а не молчаливый разбор: ошибку API должен увидеть
        # хендлер бота и сказать о ней пользователю, а не проглотить.
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    async def add_word(
        self, tg_id: int, word: str, pos: str | None = None, as_is: bool = False
    ) -> list[dict[str, Any]]:
        body = await self._call(
            "POST", "/words", tg_id, json={"word": word, "pos": pos, "as_is": as_is}
        )
        return body["entries"]

    async def quiz(self, tg_id: int, limit: int) -> list[dict[str, Any]]:
        body = await self._call("GET", "/quiz", tg_id, params={"limit": limit})
        return body["cards"]

    async def review(self, tg_id: int, card_id: int, rating: int, mode: str) -> None:
        await self._call("POST", "/review", tg_id, json={"card_id": card_id, "rating": rating, "mode": mode})

    async def report(self, tg_id: int, word_id: int, reason: str) -> None:
        await self._call("POST", "/reports", tg_id, json={"word_id": word_id, "reason": reason})

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

    async def me(self, tg_id: int, tg_name: str | None = None) -> dict[str, Any]:
        return await self._call("GET", "/me", tg_id, tg_name)

    async def create_teacher_invite(self, tg_id: int) -> dict[str, Any]:
        return await self._call("POST", "/admin/teacher-invites", tg_id)

    async def redeem_teacher_invite(self, tg_id: int, tg_name: str, code: str) -> dict[str, Any]:
        return await self._call("POST", f"/teacher-invites/{code}/redeem", tg_id, tg_name)

    async def teachers(self, tg_id: int) -> list[dict[str, Any]]:
        return await self._call("GET", "/admin/teachers", tg_id)

    async def remove_teacher(self, tg_id: int, user_id: int) -> None:
        await self._call("DELETE", f"/admin/teachers/{user_id}", tg_id)

    async def students(self, tg_id: int) -> list[dict[str, Any]]:
        return await self._call("GET", "/teacher/students", tg_id)

    async def join_class(self, tg_id: int, tg_name: str, code: str) -> dict[str, Any]:
        return await self._call("POST", f"/classes/{code}/join", tg_id, tg_name)

    async def test_reminders(self) -> list[dict[str, Any]]:
        return await self._call("GET", "/internal/test-reminders")
