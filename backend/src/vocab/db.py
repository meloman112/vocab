"""Пул asyncpg и накат миграций. ORM нет: SQL пишется руками и виден целиком."""

import logging
from pathlib import Path

import asyncpg

log = logging.getLogger(__name__)

# Миграции лежат внутри пакета, а не рядом с ним: после pip install код
# уезжает в site-packages, и путь «на два каталога вверх» указал бы в пустоту —
# миграции молча не применились бы вовсе.
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def create_pool(dsn: str) -> asyncpg.Pool:
    # min_size=1: сервис личный, держать пустые соединения незачем.
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    assert pool is not None  # create_pool возвращает Optional только при loop=None
    return pool


async def migrate(pool: asyncpg.Pool) -> None:
    """Накатывает неприменённые файлы миграций по возрастанию имени.

    Свой раннер вместо alembic: миграции здесь — плоский набор .sql без
    ветвлений и автогенерации, а alembic принёс бы каталог env.py, ревизии
    и зависимость ради того же самого.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            "create table if not exists schema_migrations ("
            " name text primary key, applied_at timestamptz not null default now())"
        )
        applied = {r["name"] for r in await conn.fetch("select name from schema_migrations")}

        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not files:
            # Пустой каталог здесь означает сломанную сборку, а не «нечего
            # накатывать»: без падения сервис поднялся бы на пустой базе.
            raise RuntimeError(f"нет миграций в {MIGRATIONS_DIR}")

        for path in files:
            if path.name in applied:
                continue
            log.info("применяю миграцию %s", path.name)
            # Каждая миграция — одна транзакция: упавшая не оставляет
            # половину схемы и не попадает в schema_migrations.
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "insert into schema_migrations (name) values ($1)", path.name
                )
