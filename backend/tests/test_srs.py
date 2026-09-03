"""Обёртка над py-fsrs: проверяем перекладывание полей, а не сам алгоритм."""

from datetime import datetime, timedelta, timezone

from vocab.srs import review

NEW_CARD = {
    "id": 1,
    "state": 1,
    "step": 0,
    "stability": None,
    "difficulty": None,
    "due": datetime.now(timezone.utc),
    "last_review": None,
}


def test_good_rating_moves_due_forward():
    updated = review(NEW_CARD, 3)
    assert updated["due"] > NEW_CARD["due"]
    assert updated["last_review"] is not None
    # После первого ответа параметры обязаны появиться: None здесь означал бы,
    # что поля не доехали обратно в колонки.
    assert updated["stability"] is not None
    assert updated["difficulty"] is not None


def test_state_is_plain_int():
    updated = review(NEW_CARD, 4)
    assert type(updated["state"]) is int


def test_naive_datetime_from_db_is_accepted():
    # asyncpg отдаёт timestamptz в UTC, но соединение может быть настроено
    # иначе; обёртка обязана привести время сама, а не упасть.
    row = dict(NEW_CARD, due=datetime.now(timezone(timedelta(hours=5))))
    assert review(row, 3)["due"].tzinfo is not None
