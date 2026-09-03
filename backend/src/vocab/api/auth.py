"""Два пути аутентификации: initData мини-аппа и статический токен."""

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, Request, status

from .. import repo
from ..config import Settings, settings

log = logging.getLogger(__name__)

# Telegram не отзывает initData: подпись живёт, пока живёт токен бота.
# Ограничение по возрасту — единственное, что мешает переиграть перехваченный
# заголовок через месяц.
INIT_DATA_MAX_AGE = 24 * 60 * 60


def parse_init_data(init_data: str, bot_token: str) -> int:
    """Проверяет HMAC-SHA256 подпись initData и возвращает tg_id.

    Алгоритм из документации Telegram: ключ — HMAC(b"WebAppData", bot_token),
    а подписывается строка вида "key=value\\n..." из всех полей кроме hash,
    отсортированных по имени.
    """
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", "")
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData без подписи")

    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    # compare_digest, а не ==: сравнение строк выходит на первом различии
    # и по времени ответа подпись можно подобрать побайтно.
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "подпись initData неверна")

    auth_date = int(fields.get("auth_date", "0"))
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData просрочен")

    user_json = fields.get("user")
    if not user_json:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData без пользователя")

    return int(json.loads(user_json)["id"])


def _tg_id_from_token(
    cfg: Settings, token: str, tg_id_header: str | None
) -> int:
    if not hmac.compare_digest(token.encode(), cfg.api_token.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "неверный токен")
    # Букмарклет и MCP работают от владельца и tg_id не знают. Бот знает и
    # присылает — этим одна строка кода оставляет дверь мультиюзеру открытой,
    # не добавляя его сейчас.
    if tg_id_header:
        return int(tg_id_header)
    return cfg.owner_tg_id


async def current_user(
    request: Request,
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
    x_token: str | None = Header(default=None, alias="X-Token"),
    x_tg_id: str | None = Header(default=None, alias="X-Tg-Id"),
) -> int:
    """Возвращает users.id. Заголовка нет вовсе — 401, а не 400."""
    cfg = settings()
    if x_init_data:
        tg_id = parse_init_data(x_init_data, cfg.bot_token)
    elif x_token:
        tg_id = _tg_id_from_token(cfg, x_token, x_tg_id)
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "нужен X-Init-Data или X-Token")

    async with request.app.state.pool.acquire() as conn:
        return await repo.ensure_user(conn, tg_id)


async def service_only(
    x_token: str | None = Header(default=None, alias="X-Token"),
) -> None:
    """Для служебных ручек, которые зовёт только бот, но не мини-апп."""
    cfg = settings()
    if not x_token or not hmac.compare_digest(x_token.encode(), cfg.api_token.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "неверный токен")
