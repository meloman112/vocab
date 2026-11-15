"""Кому и что пишет бот. Ошибка здесь — либо спам, либо сгоревшая серия."""

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
