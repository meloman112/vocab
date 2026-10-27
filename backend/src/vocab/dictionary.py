"""Добавление: текст пользователя → леммы → общий словарь → личные карточки.

ИИ зовётся в двух случаях: лемма новая для общего словаря или прислано
несколько слов и в них надо найти фразы. Всё остальное — офлайн и из базы.
"""

from typing import Any

import asyncpg

from . import enrich, lexicon, repo
from .config import Settings


class Rejected(Exception):
    """Текст не принят. Сообщение уходит пользователю как есть."""


async def add_text(
    pool: asyncpg.Pool, cfg: Settings, user_id: int, text: str
) -> list[dict[str, Any]]:
    entries = []
    for lemma, form_note in await _items(pool, cfg, user_id, repo.normalize_word(text)):
        word = await _ensure_word(pool, cfg, user_id, lemma)
        async with pool.acquire() as conn:
            created = await repo.add_card(conn, user_id, word["id"])
            count = await repo.learners(conn, word["id"])
        entries.append(
            {**dict(word), "form_note": form_note, "created": created, "learners": count}
        )
    return entries


async def _items(
    pool: asyncpg.Pool, cfg: Settings, user_id: int, text: str
) -> list[tuple[str, str | None]]:
    """Пары (лемма, пояснение формы). Предложение целиком не учим — только
    устойчивые фразы из него."""
    if " " not in text:
        if not lexicon.is_word(text):
            raise Rejected(f"Не знаю английского слова «{text}».")
        analysis = lexicon.analyze(text)
        return [(analysis.lemma, analysis.form_note)]

    await _spend_llm(pool, cfg, user_id)
    phrases = await enrich.find_phrases(cfg, text)
    if not phrases:
        raise Rejected("Устойчивых фраз здесь нет. Отдельное слово пришли одно.")
    return [(phrase, None) for phrase in phrases]


async def _ensure_word(
    pool: asyncpg.Pool, cfg: Settings, user_id: int, lemma: str
) -> asyncpg.Record:
    async with pool.acquire() as conn:
        word = await repo.get_word(conn, lemma)
    if word is not None and word["banned"]:
        raise Rejected(f"«{lemma}» в словарь не добавляется.")
    if word is not None:
        return word

    await _spend_llm(pool, cfg, user_id)
    fields = await enrich.fetch_word(cfg, lemma)
    async with pool.acquire() as conn:
        return await repo.save_word(conn, lemma, lexicon.zipf(lemma), fields)


async def _spend_llm(pool: asyncpg.Pool, cfg: Settings, user_id: int) -> None:
    async with pool.acquire() as conn:
        used = await repo.spend_llm(conn, user_id, cfg.tz)
    if used > cfg.llm_daily_limit:
        raise Rejected("На сегодня лимит новых слов исчерпан. Приходи завтра.")
