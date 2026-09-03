"""Разбор ответа DeepSeek. Модель отвечает свободным текстом, поэтому
падать здесь должно громко и предсказуемо."""

import json

import pytest

from vocab.enrich import parse_answer

FULL = {
    "translation": "устойчивый",
    "ipa": "rɪˈzɪliənt",
    "pos": "adjective",
    "example": "The system is resilient to failures.",
    "example_ru": "Система устойчива к сбоям.",
}


def test_full_answer_is_parsed():
    assert parse_answer(json.dumps(FULL)) == FULL


def test_extra_fields_are_dropped():
    # Лишнее поле в ответе не должно доехать до колонок: молча проигнорировать
    # его безопаснее, чем уронить обогащение из-за болтливой модели.
    assert parse_answer(json.dumps({**FULL, "note": "лишнее"})) == FULL


def test_missing_field_raises():
    # Валидный JSON без перевода — самый вероятный кривой ответ. Без проверки
    # карточка уехала бы в 'ready' пустой и чинить её было бы нечем.
    with pytest.raises(ValueError):
        parse_answer(json.dumps({**FULL, "translation": ""}))


def test_non_json_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_answer("извини, не понял")
