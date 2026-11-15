"""Команды класса в группе: разбор номеров и текст отчёта."""

from vocab.bot.groups import parse_exercises, report_text


def test_parse_ranges_and_lists_sorted_unique():
    assert parse_exercises("31, 26-28 27") == [26, 27, 28, 31]


def test_parse_ignores_words():
    assert parse_exercises("упражнения") == []


def test_parse_dash_variants():
    assert parse_exercises("5 – 7") == [5, 6, 7]


def test_parse_huge_range_is_capped():
    assert len(parse_exercises("1-999999")) == 201


REPORT = {
    "exercises": [26, 27, 28],
    "total": 45,
    "students": [
        {"name": "Тимур", "done": 0, "first_try": 0, "top_mistake": None, "top_count": None},
        {"name": "Мадина", "done": 20, "first_try": 15, "top_mistake": None, "top_count": None},
        {"name": "Али", "done": 45, "first_try": 38, "top_mistake": "Не то время", "top_count": 5},
    ],
    "hard_items": [{"item": "26-3", "students": 3}],
}


def test_report_sorts_by_done_and_shows_top_mistake():
    lines = report_text(REPORT).split("\n")
    assert lines[0] == "📊 Домашка: упражнения 26, 27, 28 (45 заданий)"
    assert lines[2] == "• Али — 45 из 45, с первого раза 38 (84%), чаще всего: Не то время ×5"
    assert lines[3] == "• Мадина — 20 из 45, с первого раза 15 (75%)"
    assert lines[4] == "• Тимур — не начинал"


def test_report_lists_hard_items_with_human_numbers():
    assert report_text(REPORT).endswith("Трудные задания:\nупр. 26 №4 — ошиблись 3")


def test_report_without_hard_items_has_no_section():
    assert "Трудные" not in report_text({**REPORT, "hard_items": []})
