"""Контент тетради: сервер знает каждое задание и число пропусков в нём.

Ключи ответов проверяет scripts/grammar-keys.ts в мини-аппе — там движок.
"""

from vocab import grammar


def test_all_exercises_from_the_book():
    content = grammar.content()
    assert sorted(content.exercises) == list(range(1, 135))


def test_item_keys_match_old_miniapp():
    """Ключ «упражнение-индекс с нуля» — как в CloudStorage прежней тетради:
    иначе перенесённый прогресс не встал бы на свои задания."""
    items = grammar.content().items
    first = items["4-0"]
    assert (first.exercise, first.n, first.slots) == (4, 1, 2)
    assert "15-19" in items and "15-20" not in items


def test_every_item_has_a_gap():
    assert all(item.slots > 0 for item in grammar.content().items.values())


def test_plain_shows_book_brackets():
    assert grammar.plain("I {|to take|C1} my brother. {You|to study|CP} now?") == (
        "I (to take) my brother. You (to study) now?"
    )
    assert grammar.plain("The woman {||=who|that} helped me.") == "The woman ___ helped me."
