"""Варианты ответа и пропуск: ошибка здесь даёт тест с двумя правильными
ответами или без правильного вовсе."""

import random

from vocab.quiz import BLANK, choices, cloze

CARD = {"word": "big", "translation": "большой, крупный", "pos": "adjective"}
POOL = [
    {"lemma": "large", "translation": "крупный", "pos": "adjective"},
    {"lemma": "big", "translation": "важный", "pos": "adjective"},
    {"lemma": "small", "translation": "маленький", "pos": "adjective"},
    {"lemma": "red", "translation": "красный", "pos": "adjective"},
    {"lemma": "run", "translation": "бежать", "pos": "verb"},
    {"lemma": "old", "translation": "старый", "pos": "adjective"},
]


def test_choices_contain_answer_once_and_skip_synonyms():
    options = choices(CARD, POOL, "translation", random.Random(1))
    assert options.count("большой, крупный") == 1
    assert "крупный" not in options  # синоним — второй правильный ответ
    assert "важный" not in options  # та же лемма другой частью речи
    assert len(options) == 4


def test_choices_prefer_same_part_of_speech():
    options = choices(CARD, POOL, "lemma", random.Random(1))
    assert set(options) == {"big", "small", "red", "old"}


def test_choices_survive_tiny_pool():
    assert choices(CARD, [], "translation", random.Random(1)) == ["большой, крупный"]


def test_cloze_finds_irregular_form():
    gap = cloze("go", "go · went · gone", [{"en": "She went home.", "ru": "Она пошла домой."}])
    assert gap == {"text": f"She {BLANK} home.", "answer": "went", "ru": "Она пошла домой."}


def test_cloze_inflects_phrase_head():
    gap = cloze("give up", "", [{"en": "He gave up smoking.", "ru": "Он бросил курить."}])
    assert gap["answer"] == "gave up"
    assert gap["text"] == f"He {BLANK} smoking."


def test_cloze_ignores_word_inside_other_word():
    assert cloze("cat", "", [{"en": "A category of things.", "ru": "-"}]) is None
