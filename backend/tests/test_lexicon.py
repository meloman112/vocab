"""Форма → лемма. От этого зависит, что went и gone — одна карточка go."""

import pytest
from wordfreq import zipf_frequency

from vocab.lexicon import analyze, is_word, lemma_zipf, rank, rank_label


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


@pytest.mark.parametrize("word", ["number", "data", "overcome"])
def test_rare_false_lemma_is_ignored(word):
    assert analyze(word).lemma == word


def test_plural_noun_is_not_only_a_verb_form():
    note = analyze("bicycles").form_note
    assert note.startswith("множественное число") and "he/she/it" in note


def test_irregular_form_shared_by_v2_and_v3():
    assert "V2" in analyze("left").form_note and "V3" in analyze("left").form_note


def test_lemma_has_no_note():
    assert analyze("go").form_note is None


def test_gibberish_is_not_a_word():
    assert not is_word("asdfg")
    assert not is_word("слово")
    assert is_word("resilient")


def test_lemma_frequency_counts_all_forms():
    # went и gone частые сами по себе: без суммы go выглядел бы реже, чем есть.
    assert lemma_zipf("go") > zipf_frequency("go", "en")


def test_foreign_forms_do_not_inflate_frequency():
    # number — не форма numb, under-went — не under и went.
    assert lemma_zipf("numb") < 4
    assert lemma_zipf("undergo") < 5


def test_rank_orders_by_frequency():
    assert rank(lemma_zipf("the")) == 1
    assert rank(lemma_zipf("go")) < rank(lemma_zipf("reliable")) < rank(lemma_zipf("redundant"))


def test_rank_labels():
    assert rank_label(lemma_zipf("go")) == "топ-100"
    assert rank_label(lemma_zipf("reliable")) == "топ-5000"
    assert rank_label(0) == "реже топ-20000"
    assert rank_label(lemma_zipf("go"), "A1") == "A1 · топ-100"
