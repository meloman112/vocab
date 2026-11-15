"""Контрольная на уроке: что видит группа и когда сдача ещё принимается."""

from datetime import UTC, datetime, timedelta

from vocab.api.classwork import SUBMIT_GRACE, _can_submit, _summary
from vocab.bot.exams import exam_keyboard, render_test, split_message, summary_text

QUESTIONS = [
    {"parts": ["She ", {"answers": ["likes"], "hint": ""}, " tea."]},
    {"parts": [{"answers": ["I"], "hint": ""}, " ", {"answers": ["am"], "hint": ""}, " here."]},
]


def row(name, answers):
    return {"name": name, "answers": answers}


def test_summary_sorted_by_score_with_missing_last_and_hardest_questions():
    summary = {
        "title": "Unit 3", "total": 3,
        "students": [
            {"name": "Али", "score": 2}, {"name": "Тимур", "score": None}, {"name": "Мадина", "score": 3},
        ],
        "hard": [{"question": 2, "correct": 1, "answered": 2}],
    }
    assert summary_text(summary).splitlines() == [
        "⏰ Контрольная «Unit 3» закончена", "",
        "• Мадина — 3 из 3", "• Али — 2 из 3", "• Тимур — не сдал",
        "", "Труднее всего: №2 (верно 1 из 2)",
    ]


def test_summary_without_hard_questions_has_no_last_line():
    summary = {"title": "T", "total": 1, "students": [{"name": "Али", "score": 1}], "hard": []}
    assert "Труднее" not in summary_text(summary)


def test_summary_counts_a_question_right_only_if_all_its_gaps_are_right():
    test = {"id": 1, "chat_id": 5, "title": "T", "questions": QUESTIONS}
    rows = [row("Али", ["likes", "I", "am"]), row("Мадина", ["likes", "I", "was"]), row("Тимур", None)]
    result = _summary(test, rows, {})
    assert [(s.name, s.score) for s in result.students] == [("Али", 3), ("Мадина", 2), ("Тимур", None)]
    assert result.total == 3
    assert [(h.question, h.correct, h.answered) for h in result.hard] == [(2, 1, 2)]


def test_summary_has_no_hard_questions_when_everyone_is_right():
    test = {"id": 1, "chat_id": 5, "title": "T", "questions": QUESTIONS}
    assert _summary(test, [row("Али", ["likes", "I", "am"])], {}).hard == []


def test_submit_allowed_for_twenty_seconds_after_the_end_of_a_live_test():
    ends = datetime(2026, 1, 1, tzinfo=UTC)
    live = {"closed": True, "ends_at": ends}
    assert _can_submit(live, ends + SUBMIT_GRACE - timedelta(seconds=1))
    assert not _can_submit(live, ends + SUBMIT_GRACE)
    assert not _can_submit({"closed": True, "ends_at": None}, ends)
    assert _can_submit({"closed": False, "ends_at": None}, ends)


def test_render_skips_bad_lines_and_keeps_original_numbers():
    text, shown, skipped = render_test([("a [b]", ""), ("плохая", "нет пропуска"), ("c [d]", "")])
    assert text == "a [b]\nc [d]"
    assert shown == ["1. a [b]\n3. c [d]"]
    assert skipped == [2]


def test_long_test_is_split_into_messages_under_the_limit():
    chunks = split_message("\n".join(["x" * 100] * 100), limit=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    assert "\n".join(chunks).count("x" * 100) == 100


def test_keyboard_only_for_bound_classes_and_names_them_when_several():
    assert exam_keyboard([{"id": 1, "name": "9А", "chat_id": None}]) is None
    one = exam_keyboard([{"id": 1, "name": "9А", "chat_id": -5}])
    assert [b.text for b in one.inline_keyboard[0]] == ["▶️ 15 мин", "▶️ 20 мин", "▶️ 30 мин"]
    assert one.inline_keyboard[0][0].callback_data == "exam:1:15"
    two = exam_keyboard([{"id": 1, "name": "9А", "chat_id": -5}, {"id": 2, "name": "9Б", "chat_id": -6}])
    assert len(two.inline_keyboard) == 2
    assert two.inline_keyboard[1][2].text == "9Б ▶️ 30 мин"
