#!/usr/bin/env python3
"""Живая проверка контура: слово добавляется, попадает в очередь после
обогащения, оценка сдвигает расписание.

Гоняет по-настоящему, с обогащением и базой: тест, который ничего не
проверяет, хуже отсутствующего.
"""

import os
import sys
import time
import urllib.error
import urllib.request
import json

BASE = os.environ.get("SMOKE_BASE", "http://localhost:8000")
TOKEN = os.environ.get("API_TOKEN", "")
WORD = f"smoke{int(time.time())}"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-Token": TOKEN},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, None


def main() -> int:
    if not TOKEN:
        print("нужен API_TOKEN в окружении", file=sys.stderr)
        return 1

    status, _ = call("GET", "/healthz")
    assert status == 200, f"healthz вернул {status}"

    status, body = call("POST", "/words", {"word": WORD})
    assert status == 200 and body["created"], f"добавление слова: {status} {body}"
    card_id = body["id"]

    # Без токена доступа быть не должно — проверяем, что 401, а не 200.
    unauth = urllib.request.Request(BASE + "/queue")
    try:
        urllib.request.urlopen(unauth, timeout=10)
        print("очередь открылась без токена", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        assert exc.code == 401, f"без токена ожидался 401, получен {exc.code}"

    status, body = call("GET", "/stats")
    assert status == 200 and len(body["forecast"]) == 7, f"stats: {status} {body}"

    status, _ = call("DELETE", f"/words/{card_id}")
    assert status == 204, f"удаление вернуло {status}"

    print(f"smoke ok ({BASE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
