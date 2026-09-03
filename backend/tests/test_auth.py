"""Проверка подписи initData — единственное, что стоит между чужим
пользователем и чужим словарём."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from vocab.api.auth import parse_init_data

BOT_TOKEN = "123456:test-token"


def make_init_data(tg_id: int = 42, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAA",
        "user": json.dumps({"id": tg_id, "first_name": "T"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_valid_init_data_returns_tg_id():
    assert parse_init_data(make_init_data(777), BOT_TOKEN) == 777


def test_tampered_payload_is_rejected():
    # Меняем пользователя, оставляя подпись от прежнего: ровно то, что
    # сделал бы желающий поработать в чужом словаре.
    init_data = make_init_data(777).replace("%22id%22%3A777", "%22id%22%3A778")
    with pytest.raises(HTTPException) as exc:
        parse_init_data(init_data, BOT_TOKEN)
    assert exc.value.status_code == 401


def test_wrong_bot_token_is_rejected():
    with pytest.raises(HTTPException):
        parse_init_data(make_init_data(), "999:other")


def test_stale_init_data_is_rejected():
    old = int(time.time()) - 48 * 3600
    with pytest.raises(HTTPException):
        parse_init_data(make_init_data(auth_date=old), BOT_TOKEN)
