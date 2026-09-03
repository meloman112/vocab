"""Обёртка над py-fsrs. Своего алгоритма здесь нет и быть не должно."""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from fsrs import Card, Rating, Scheduler, State

# Дефолтные параметры FSRS. Свои появятся, когда в reviews накопится
# история и её можно будет прогнать через fsrs.Optimizer.
_scheduler = Scheduler()

# Колонки cards, которые целиком принадлежат FSRS.
FSRS_COLUMNS = ("state", "step", "stability", "difficulty", "due", "last_review")


def _utc(value: datetime | None) -> datetime | None:
    """review_card требует datetime строго в UTC и падает на любом другом.

    asyncpg отдаёт timestamptz уже в UTC, но приведение стоит одну строку
    и снимает зависимость от настроек соединения.
    """
    if value is None:
        return None
    return value.astimezone(timezone.utc)


def review(row: Mapping[str, Any], rating: int) -> dict[str, Any]:
    """Пересчитывает расписание карточки. Возвращает новые значения колонок."""
    card = Card(
        card_id=row["id"],
        state=State(row["state"]),
        step=row["step"],
        stability=row["stability"],
        difficulty=row["difficulty"],
        due=_utc(row["due"]),
        last_review=_utc(row["last_review"]),
    )
    card, _ = _scheduler.review_card(card, Rating(rating))
    updated = {name: getattr(card, name) for name in FSRS_COLUMNS}
    # state — IntEnum; asyncpg записал бы его и так, но в колонке int
    # честнее хранить int, а не enum конкретной версии библиотеки.
    updated["state"] = int(card.state)
    return updated
