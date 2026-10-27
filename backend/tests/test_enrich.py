"""Разбор ответов DeepSeek. Модель отвечает свободным текстом, поэтому
падать здесь должно громко и предсказуемо."""

import json

import pytest

from vocab.enrich import parse_phrases, parse_word

FULL = {
    "translation": "идти, ехать",
    "ipa": "ɡoʊ",
    "pos": "verb",
    "forms": "go · went · gone",
    "irregular": True,
    "examples": [
        {"en": "I go to work by bus.", "ru": "Я езжу на работу на автобусе."},
        {"en": "She has gone home.", "ru": "Она ушла домой."},
    ],
}


def test_full_answer_is_parsed():
    assert parse_word(json.dumps(FULL)) == FULL


def test_extra_fields_are_dropped():
    # Лишнее поле не должно доехать до колонок: проигнорировать его безопаснее,
    # чем уронить запрос из-за болтливой модели.
    assert parse_word(json.dumps({**FULL, "note": "лишнее"})) == FULL


def test_optional_fields_default():
    answer = {k: v for k, v in FULL.items() if k not in ("forms", "irregular")}
    parsed = parse_word(json.dumps(answer))
    assert parsed["forms"] == "" and parsed["irregular"] is False


def test_irregular_must_be_real_bool():
    # "false" строкой — истина в Python; пометить правильный глагол
    # неправильным хуже, чем не пометить.
    assert parse_word(json.dumps({**FULL, "irregular": "false"}))["irregular"] is False


def test_missing_translation_raises():
    # Валидный JSON без перевода — самый вероятный кривой ответ. Без проверки
    # слово уехало бы в общий словарь пустым, сразу всем.
    with pytest.raises(ValueError):
        parse_word(json.dumps({**FULL, "translation": ""}))


def test_no_examples_raises():
    with pytest.raises(ValueError):
        parse_word(json.dumps({**FULL, "examples": [{"en": "only english"}]}))


def test_non_json_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_word("извини, не понял")


def test_phrases_are_normalized():
    answer = json.dumps({"phrases": ["Give  Up", "more and more", " "]})
    assert parse_phrases(answer) == ["give up", "more and more"]
