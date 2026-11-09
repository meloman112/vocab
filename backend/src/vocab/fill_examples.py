"""Дописывает примеры словам наборов, заведённым из файла учителя без них.

Перевод и транскрипцию из файла не трогает — их выбрал учитель; от модели
берутся только примеры, формы и уровень. Слова идут по одному: слот модели
общий, и пачка заняла бы его на час для всех.

    docker compose exec -d api python -m vocab.fill_examples
"""

import asyncio
import logging

from . import enrich
from .config import settings
from .db import create_pool

log = logging.getLogger(__name__)


async def main() -> None:
    cfg = settings()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(message)s")
    pool = await create_pool(cfg.database_url)
    words = await pool.fetch(
        "select id, lemma, pos from words"
        " where deck is not null and examples = '[]'::jsonb and not banned order by deck_order"
    )
    log.info("без примеров: %s", len(words))
    for n, word in enumerate(words, 1):
        try:
            card = await enrich.fetch_word(cfg, word["lemma"], word["pos"])
        except enrich.EnrichError as exc:
            log.warning("%s/%s: %s, пропускаю", n, len(words), exc)
            continue
        await pool.execute(
            "update words set examples = $2, level = coalesce(level, $3),"
            " forms = case when forms = '' then $4 else forms end where id = $1",
            word["id"], card["examples"], card["level"], card["forms"],
        )
        log.info("%s/%s: %s", n, len(words), word["lemma"])
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
