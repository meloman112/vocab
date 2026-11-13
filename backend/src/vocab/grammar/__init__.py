"""Тетрадь по грамматике: упражнения из книги учителя.

Ключи ответов здесь не считаются: их строит движок мини-аппа из кода
пропуска (C3, SP, =had…). Серверу нужно знать только, какие задания
существуют и сколько в них пропусков, — чтобы не принимать мусор.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CONTENT_PATH = Path(__file__).resolve().parent / "content.json"
SLOT = re.compile(r"\{([^|}]*)\|([^|}]*)\|([^}]*)\}")


@dataclass(frozen=True)
class Item:
    key: str
    exercise: int
    n: int
    slots: int
    topic: str
    text: str


@dataclass(frozen=True)
class Content:
    raw: bytes
    etag: str
    items: dict[str, Item]
    exercises: dict[int, str]


@lru_cache
def content() -> Content:
    """Читается один раз: контент меняется только выкаткой."""
    raw = CONTENT_PATH.read_bytes()
    data = json.loads(raw)
    items: dict[str, Item] = {}
    exercises: dict[int, str] = {}
    for topic in data["topics"]:
        for ex in topic["exercises"]:
            exercises[ex["id"]] = ex["task"]
            for i, text in enumerate(ex["items"]):
                # Ключ — как в прежнем мини-аппе: упражнение и индекс с нуля.
                key = f"{ex['id']}-{i}"
                items[key] = Item(key, ex["id"], i + 1, len(SLOT.findall(text)), topic["id"], text)
    # Отдаём одними и теми же байтами: ETag избавляет телефон от повторной
    # загрузки ~400 КБ при каждом открытии тетради.
    etag = '"' + hashlib.sha256(raw).hexdigest()[:16] + '"'
    return Content(raw, etag, items, exercises)


def plain(text: str) -> str:
    """Задание текстом из книги: пропуск → «(to go)» или «___»."""
    def show(m: re.Match[str]) -> str:
        lead, bracket = m.group(1).strip(), m.group(2).strip()
        hint = f"({bracket})" if bracket and bracket != "…" else "___"
        return f"{lead} {hint}".strip()
    return SLOT.sub(show, text)
