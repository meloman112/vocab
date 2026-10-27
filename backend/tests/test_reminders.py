"""Кому и что пишет бот. Ошибка здесь — либо спам, либо сгоревшая серия."""

from vocab.bot.reminders import reminder_text


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
