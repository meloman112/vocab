"""Виджеты чата: шаблоны и данные должны влезать в лимиты Bot API, иначе
Telegram отвечает INPUT_MEDIA_WIDGET_TOO_LARGE и пользователь не видит ничего."""

import zlib

import pytest

from vocab.bot.chat import Quiz, card_data, first_forms, question
from vocab.bot.widget import MAX_DATA, TEMPLATES, dump, template

NAMES = sorted(p.stem for p in TEMPLATES.glob("*.html") if not p.stem.startswith("_"))


@pytest.mark.parametrize("name", NAMES)
def test_template_fits_telegram_limits(name):
    html = template(name).encode()
    assert len(html) <= 32768
    assert len(zlib.compress(html, 9)) <= 4096


def test_long_card_is_trimmed_to_one_kilobyte():
    example = {"en": "x" * 300, "ru": "я" * 300}
    entry = {
        "lemma": "incorporate", "ipa": "ɪnˈkɔːpəreɪt", "pos": "verb", "irregular": False,
        "forms": "", "form_note": None, "translation": "включать, " * 30, "top": "топ-5000",
        "learners": 3, "created": True, "examples": [example] * 3,
    }
    data = card_data(entry)
    assert len(dump(data).encode()) <= MAX_DATA
    assert data["e"], "хотя бы один пример должен остаться"


def card(i, word="book"):
    return {"id": i, "word": word, "pos": "noun", "homonym": False, "translation": "книга",
            "choices_ru": ["стол", "книга", "дом", "кот"]}


def test_quiz_alternates_choice_and_spelling():
    quiz = Quiz([card(1), card(2)])
    assert question(quiz)["k"] == "c" and question(quiz)["a"] == 1
    quiz.index = 1
    assert question(quiz) == {"id": 2, "n": [2, 2], "k": "s", "q": "книга", "a": "book"}
    quiz.index, quiz.right = 2, 1
    assert question(quiz) == {"end": [1, 2]}


def test_long_word_is_not_spelled():
    quiz = Quiz([card(1), card(2, "accomplishment")], index=1)
    assert question(quiz)["k"] == "c"


def test_first_forms_take_first_variant():
    assert first_forms("get · got · got/gotten") == ["get", "got", "got"]
