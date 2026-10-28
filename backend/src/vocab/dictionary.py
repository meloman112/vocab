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
    text = repo.normalize_word(text)
    for lemma, analysis in await _items(pool, cfg, user_id, text):
        word = await _ensure_word(pool, cfg, user_id, lemma)
        # Пометка выбирается по части речи карточки, а не по слову вообще:
        # bicycles у карточки bicycle (noun) — множественное число, без he/she/it.
        note = analysis.note_for(word["pos"]) if analysis else None
        async with pool.acquire() as conn:
            created = await repo.add_card(conn, user_id, word["id"])
            count = await repo.learners(conn, word["id"])
        entries.append({
            **dict(word),
            "form_note": f"{text} — {note}" if note else None,
            "created": created,
            "learners": count,
            "top": lexicon.rank_label(word["zipf"], word["level"]),
        })
    return entries


async def _items(
    pool: asyncpg.Pool, cfg: Settings, user_id: int, text: str
) -> list[tuple[str, lexicon.Analysis | None]]:
    """Пары (лемма, разбор присланной формы). Предложение целиком не учим — только
    устойчивые фразы из него."""
    # Готовое слово или фраза из общего словаря берутся как есть: составители
    # учебных списков считают interesting и evening самостоятельными словами,
    # а lemminflect свёл бы их к interest и even.
    async with pool.acquire() as conn:
        if await repo.get_word(conn, text) is not None:
            return [(text, None)]
    if " " not in text:
        if not lexicon.is_word(text):
            raise Rejected(f"Не знаю английского слова «{text}».")
        analysis = lexicon.analyze(text)
        return [(analysis.lemma, analysis)]

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
    # Частоты фраз wordfreq не знает и выдумывает их из отдельных слов
    # («up give» = «give up»), поэтому для фразы верим оценке модели.
    zipf = fields["zipf"] if " " in lemma else lexicon.lemma_zipf(lemma)
    async with pool.acquire() as conn:
        return await repo.save_word(conn, lemma, zipf, fields)


async def backfill_zipf(pool: asyncpg.Pool) -> None:
    """Частота для слов, перенесённых из личных карточек миграцией 002:
    в SQL её не посчитать, а с нулём они навсегда ушли бы в конец выдачи.
    После первого запуска список пуст, и это один быстрый select."""
    async with pool.acquire() as conn:
        for lemma in await repo.words_without_zipf(conn):
            await repo.set_zipf(conn, lemma, lexicon.lemma_zipf(lemma))


async def _spend_llm(pool: asyncpg.Pool, cfg: Settings, user_id: int) -> None:
    async with pool.acquire() as conn:
        used = await repo.spend_llm(conn, user_id, cfg.tz)
    if used > cfg.llm_daily_limit:
        raise Rejected("На сегодня лимит новых слов исчерпан. Приходи завтра.")
