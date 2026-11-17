"""Кому и что пишет бот. Ошибка здесь — либо спам, либо сгоревшая серия."""

from datetime import UTC, datetime

from vocab.api.routes import at_local_hours
from vocab.bot.reminders import digest_text, reminder_text


def target(gap, due=5, streak=3):
    return {"tg_id": 1, "gap": gap, "due": due, "streak": streak}


def test_streak_at_risk_in_the_evening():
    assert "сгорит" in reminder_text(target(1), evening=True)


def test_streak_reminder_without_due_words_offers_new_ones():
    assert "новые слова" in reminder_text(target(1, due=0), evening=False)


def test_comeback_only_on_chosen_days_and_only_in_the_morning():
    assert reminder_text(target(2), evening=False)
    assert reminder_text(target(2), evening=True) is None
    assert reminder_text(target(5), evening=False) is None


def test_silence_after_two_weeks():
    assert reminder_text(target(14), evening=False)
    assert reminder_text(target(15), evening=False) is None


def test_never_reviewed_hears_only_about_due_words():
    assert reminder_text(target(None), evening=False)
    assert reminder_text(target(None, due=0), evening=False) is None


def student(name, done, first_try, top_mistake=None, top_count=None):
    return {"name": name, "done": done, "first_try": first_try,
            "top_mistake": top_mistake, "top_count": top_count}


def test_digest_lists_students_and_hard_items():
    text = digest_text({
        "students": [student("Али", 120, 102, "Не то время", 12), student("Вера", 40, 37, "Опечатка", 3)],
        "hard_items": [{"item": "22-3", "students": 3}, {"item": "30-1", "students": 2}],
        "teachers": [1],
    })
    assert "Занимались: 2" in text
    assert "Али — 120 заданий, с первого раза 85%. Чаще всего: Не то время (12)" in text
    assert "• упр. 22 №4 — 3 уч." in text
    assert "• упр. 30 №2 — 2 уч." in text


def test_digest_student_without_mistakes_has_no_most_common_part():
    text = digest_text({"students": [student("Вера", 10, 10)], "hard_items": [], "teachers": [1]})
    assert "Вера — 10 заданий, с первого раза 100%" in text
    assert "Чаще всего" not in text
    assert "Ошиблись" not in text


def test_digest_is_silent_on_an_empty_week():
    assert digest_text({"students": [], "hard_items": [], "teachers": [1]}) is None


def test_reminder_goes_to_those_whose_local_hour_it_is():
    rows = [{"tg_id": 1, "tz": "Asia/Tashkent"}, {"tg_id": 2, "tz": "Europe/Berlin"}, {"tg_id": 3, "tz": "UTC"}]
    # 04:00 UTC зимой: в Ташкенте 09:00, в Берлине 05:00.
    now = datetime(2026, 1, 15, 4, 0, tzinfo=UTC)
    assert [(r["tg_id"], hour) for r, hour in at_local_hours(rows, [9, 20], now)] == [(1, 9)]
    # 19:00 UTC: в Берлине 20:00 — последний час дня, в Ташкенте уже полночь.
    now = datetime(2026, 1, 15, 19, 0, tzinfo=UTC)
    assert [(r["tg_id"], hour) for r, hour in at_local_hours(rows, [9, 20], now)] == [(2, 20)]


def test_half_hour_zone_is_reminded_once_within_its_hour():
    rows = [{"tg_id": 1, "tz": "Asia/Kolkata"}]
    assert at_local_hours(rows, [9], datetime(2026, 1, 15, 3, 0, tzinfo=UTC)) == []
    assert at_local_hours(rows, [9], datetime(2026, 1, 15, 4, 0, tzinfo=UTC)) == [(rows[0], 9)]
    assert at_local_hours(rows, [9], datetime(2026, 1, 15, 5, 0, tzinfo=UTC)) == []
