"""Фоном разбирает словарь: с чем слово путают и как различать (words.contrast).

Идёт по одному слову и только когда модель свободна: слот общий, а карточку
ждёт человек. Сначала слова, которые кто-то учит, потом наборы, потом
остальное; новые слова попадают в начало очереди сами.
"""

import asyncio
import logging

import asyncpg

from . import enrich
from .config import Settings

log = logging.getLogger(__name__)

IDLE = 600

NEXT_WORD = """
    select id, lemma, pos, translation from words w
    where contrast is null and not banned and id <> all($1::bigint[])
    order by exists (select 1 from cards c where c.word_id = w.id) desc, deck_order nulls last, id
    limit 1
"""


async def run(pool: asyncpg.Pool, cfg: Settings) -> None:
    # Не ответившее слово пропускается до перезапуска, а не мучает модель по кругу.
    failed: list[int] = []
    while True:
        while enrich.in_flight:
            await asyncio.sleep(1)
        word = await pool.fetchrow(NEXT_WORD, failed)
        if word is None:
            await asyncio.sleep(IDLE)
            continue
        try:
            contrast = await enrich.fetch_contrast(cfg, word["lemma"], word["pos"], word["translation"])
        except enrich.EnrichError as exc:
            log.warning("различия %s: %s", word["lemma"], exc)
            failed.append(word["id"])
            continue
        await pool.execute("update words set contrast = $2 where id = $1", word["id"], contrast)
        log.info("различия %s: %s", word["lemma"], ", ".join(o["word"] for o in contrast["others"]) or "—")


def start(pool: asyncpg.Pool, cfg: Settings) -> asyncio.Task:
    task = asyncio.create_task(run(pool, cfg))
    task.add_done_callback(_report)
    return task


def _report(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        log.error("заполнение различий упало", exc_info=task.exception())
