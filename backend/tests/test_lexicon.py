"""Форма → лемма. От этого зависит, что went и gone — одна карточка go."""

import pytest

from vocab.lexicon import analyze, is_word


@pytest.mark.parametrize(
    ("word", "lemma", "note"),
    [
        ("reading", "read", "форма на -ing"),
        ("went", "go", "V2"),
        ("gone", "go", "V3"),
        ("children", "child", "множественное"),
        ("better", "good", "сравнительная"),
        # Глагол важнее существительного: saw — это see, а не «пила».
        ("saw", "see", "V2"),
    ],
)
def test_form_is_reduced_to_lemma(word, lemma, note):
    result = analyze(word)
    assert result.lemma == lemma
    assert note in result.form_note


def test_irregular_form_shared_by_v2_and_v3():
    assert "V2" in analyze("left").form_note and "V3" in analyze("left").form_note


def test_lemma_has_no_note():
    assert analyze("go").form_note is None


def test_gibberish_is_not_a_word():
    assert not is_word("asdfg")
    assert not is_word("слово")
    assert is_word("resilient")
