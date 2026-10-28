"""Какая из частей речи леммы достаётся пользователю: a book «книга» и
to book «бронировать» — разные карточки, и ошибиться тут значит научить
«прошедшему времени от книги»."""

import asyncio
import contextlib
from types import SimpleNamespace

import pytest

from vocab import dictionary, enrich, lexicon, repo

CFG = SimpleNamespace(tz="UTC", llm_daily_limit=100)


def card(lemma, pos, translation, banned=False):
    return {"lemma": lemma, "pos": pos, "translation": translation, "ipa": "", "forms": "",
            "irregular": False, "examples": [], "zipf": 4.0, "level": "A1", "banned": banned}


class Store:
    """Общий словарь и карточки в памяти вместо Postgres."""

    def __init__(self, *words):
        self.words = [{**w, "id": i} for i, w in enumerate(words, 1)]
        self.cards = set()
        self.asked = []  # (lemma, pos) — с чем звали модель

    async def get_senses(self, conn, lemma):
        return [w for w in self.words if w["lemma"] == lemma]

    async def get_word(self, conn, lemma):
        senses = await self.get_senses(conn, lemma)
        return senses[0] if senses else None

    async def save_word(self, conn, lemma, zipf, fields):
        word = {**card(lemma, fields["pos"], fields["translation"]), "id": len(self.words) + 1}
        self.words.append(word)
        return word

    async def add_card(self, conn, user_id, word_id):
        created = (user_id, word_id) not in self.cards
        self.cards.add((user_id, word_id))
        return created

    async def learners(self, conn, word_id):
        return 1

    async def spend_llm(self, conn, user_id, tz):
        return 1


class Pool:
    @contextlib.asynccontextmanager
    async def acquire(self):
        yield None


@pytest.fixture
def store(monkeypatch):
    def make(*words, model=None):
        s = Store(*words)
        for name in ("get_senses", "get_word", "save_word", "add_card", "learners", "spend_llm"):
            monkeypatch.setattr(repo, name, getattr(s, name))

        async def fetch_word(cfg, lemma, pos=None):
            s.asked.append((lemma, pos))
            if model is None:
                raise enrich.EnrichError("нет ответа")
            return model(lemma, pos)

        monkeypatch.setattr(enrich, "fetch_word", fetch_word)
        monkeypatch.setattr(lexicon, "rank_label", lambda zipf, level=None: "топ")
        return s
    return make


def answer(translation, pos):
    return lambda lemma, asked: {**card(lemma, pos, translation), "zipf": 4.0}


def add(text, pos=None):
    return asyncio.run(dictionary.add_text(Pool(), CFG, 1, text, pos))[0]


BOOK = card("book", "noun", "книга")


def test_plural_keeps_noun_and_offers_verb(store):
    s = store(BOOK)
    entry = add("books")
    assert (entry["pos"], entry["form_note"]) == ("noun", "books — множественное число")
    assert entry["others"] == [{"pos": "verb", "translation": None}]
    assert s.asked == []


def test_verb_only_form_creates_verb_sense(store):
    # booked — только глагол: показать «книгу» с «прошедшим временем» нельзя.
    s = store(BOOK, model=answer("бронировать", "verb"))
    entry = add("booked")
    assert (entry["lemma"], entry["pos"], entry["translation"]) == ("book", "verb", "бронировать")
    assert entry["form_note"] == "booked — прошедшее время (V2) / третья форма, причастие прошедшего времени (V3)"
    assert s.asked == [("book", "verb")]
    assert entry["others"] == [{"pos": "noun", "translation": "книга"}]


def test_known_verb_sense_is_reused(store):
    s = store(BOOK, card("book", "verb", "бронировать"))
    assert add("booking")["translation"] == "бронировать"
    assert add("books")["translation"] == "книга"
    assert s.asked == []


@pytest.mark.parametrize(("text", "pos"), [("to book", "verb"), ("a book", "noun")])
def test_marker_chooses_part_of_speech(store, text, pos):
    store(BOOK, card("book", "verb", "бронировать"))
    entry = add(text)
    assert (entry["lemma"], entry["pos"]) == ("book", pos)


def test_article_takes_noun_lemma():
    # the left — «левая сторона», а не прошедшее время от leave.
    assert lexicon.lemma_as("left", "noun") == "left"
    assert lexicon.lemma_as("children", "noun") == "child"


def test_base_form_trusts_dictionary(store):
    # lemminflect знает please только глаголом, словарь — междометием.
    s = store(card("please", "interjection", "пожалуйста"))
    assert add("please")["pos"] == "interjection"
    assert s.asked == []


def test_button_adds_chosen_sense(store):
    s = store(BOOK, model=answer("бронировать", "verb"))
    entry = add("book", pos="verb")
    assert (entry["pos"], entry["form_note"]) == ("verb", None)
    assert s.asked == [("book", "verb")]


def test_model_failure_on_form_falls_back_to_main_sense(store):
    store(BOOK)
    assert add("booked")["translation"] == "книга"


def test_model_failure_on_explicit_choice_is_reported(store):
    store(BOOK)
    with pytest.raises(enrich.EnrichError):
        add("to book")


def test_banned_lemma_is_rejected_in_any_form(store):
    store(card("book", "noun", "книга", banned=True))
    with pytest.raises(dictionary.Rejected):
        add("booked")


@pytest.mark.parametrize(("text", "pos"), [("to apple", None), ("asdfg", "verb")])
def test_impossible_part_of_speech_is_rejected_without_model(store, text, pos):
    s = store(card("apple", "noun", "яблоко"), model=answer("яблоко", "noun"))
    with pytest.raises(dictionary.Rejected):
        add(text, pos)
    assert s.asked == []
