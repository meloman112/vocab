"""Добавление: текст пользователя → леммы → общий словарь → личные карточки.

ИИ зовётся в двух случаях: лемма новая для общего словаря (или новая часть
речи у известной леммы) или прислано несколько слов и в них надо найти
фразы. Всё остальное — офлайн и из базы.
"""

import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from . import enrich, lexicon, repo
from .config import Settings

# «to book» — это глагол, «a book» — существительное: так пользователь сам
# говорит, какое из значений ему нужно.
MARKED_RE = re.compile(r"^(to|a|an|the) ([a-z][a-z'-]*)$")
MARKED_POS = {"to": "verb", "a": "noun", "an": "noun", "the": "noun"}
POS_NAMES = {"noun": "существительное", "verb": "глагол",
             "adjective": "прилагательное", "adverb": "наречие"}


class Rejected(Exception):
    """Текст не принят. Сообщение уходит пользователю как есть."""


class Misspelled(Rejected):
    """Похоже на опечатку. Клиент предлагает исправление и «добавить как есть»."""

    def __init__(self, word: str, suggestion: str) -> None:
        super().__init__(f"Слова «{word}» нет в словаре. Может, {suggestion}?")
        self.suggestion = suggestion


@dataclass(frozen=True)
class Item:
    """Что добавить: лемма и, если известно, какая из её частей речи."""

    lemma: str
    pos: str | None = None
    # pos назван явно или следует из формы (booked — только глагол): такое
    # значение заводится, даже если у леммы в словаре уже есть другое.
    strict: bool = False
    # Разбор присланной формы — для пометки «books — множественное число».
    analysis: lexicon.Analysis | None = None
    # Какими частями речи может быть присланное: из них предлагаются
    # остальные значения леммы.
    parts: tuple[str, ...] = ()


async def add_text(
    pool: asyncpg.Pool,
    cfg: Settings,
    user_id: int,
    text: str,
    pos: str | None = None,
    as_is: bool = False,
) -> list[dict[str, Any]]:
    """pos — когда пользователь выбрал значение кнопкой «ещё: to book»;
    as_is — нажал «добавить как есть» под подсказкой опечатки."""
    entries = []
    text = repo.normalize_word(text)
    for item in await _items(pool, cfg, user_id, text, pos, as_is):
        word = await _ensure_word(pool, cfg, user_id, item)
        # Пометка выбирается по части речи карточки, а не по слову вообще:
        # bicycles у карточки bicycle (noun) — множественное число, без he/she/it.
        note = item.analysis.note_for(word["pos"]) if item.analysis else None
        async with pool.acquire() as conn:
            created = await repo.add_card(conn, user_id, word["id"])
            count = await repo.learners(conn, word["id"])
            senses = await repo.get_senses(conn, word["lemma"])
        entries.append({
            **dict(word),
            "form_note": f"{text} — {note}" if note else None,
            "created": created,
            "learners": count,
            "top": lexicon.rank_label(word["zipf"], word["level"]),
            "others": _others(word, senses, item.parts),
        })
    return entries


async def lookup(pool: asyncpg.Pool, cfg: Settings, user_id: int, text: str) -> dict[str, Any]:
    """Перевод выделенного в мини-аппе: как add_text, только карточка не
    заводится — её добавляют отдельной кнопкой, если слово стоит учить.

    Новое для общего словаря слово так же уходит в модель и остаётся в
    словаре: второй раз его переведут мгновенно и без лимита.

    Несколько слов, которых нет в словаре фразой, — предложение: его
    модель переводит целиком (kind="text"), карточки у такого нет."""
    raw = " ".join(text.split())
    text = repo.normalize_word(raw)
    if " " in text:
        async with pool.acquire() as conn:
            known = await repo.get_word(conn, text) is not None
        if not known:
            return {"kind": "text", "text": raw, "translation": await _translate(cfg, user_id, raw)}
    # as_is: в учебнике опечаток нет, а «может, вы имели в виду» здесь некуда показать.
    item = (await _items(pool, cfg, user_id, text, None, as_is=True))[0]
    word = await _ensure_word(pool, cfg, user_id, item)
    note = item.analysis.note_for(word["pos"]) if item.analysis else None
    async with pool.acquire() as conn:
        saved = await repo.has_card(conn, user_id, word["id"])
    return {"kind": "word", **dict(word), "form_note": f"{text} — {note}" if note else None, "saved": saved}


# Одни и те же предложения учебника выделяют многие ученики: перевод
# запоминается в процессе. Перезапуск его теряет — это не страшно.
_TRANSLATIONS: OrderedDict[str, str] = OrderedDict()
_TRANSLATIONS_MAX = 5000
# Сколько переводов сделал пользователь сегодня: (user_id, дата) → число.
_TRANSLATED: dict[tuple[int, date], int] = {}


async def _translate(cfg: Settings, user_id: int, text: str) -> str:
    cached = _TRANSLATIONS.get(text)
    if cached is not None:
        _TRANSLATIONS.move_to_end(text)
        return cached
    today = datetime.now(ZoneInfo(cfg.tz)).date()
    key = (user_id, today)
    if _TRANSLATED.get(key, 0) >= cfg.translate_daily_limit:
        raise Rejected("На сегодня лимит переводов предложений исчерпан. Отдельные слова переводятся как раньше.")
    for old in [k for k in _TRANSLATED if k[1] != today]:
        del _TRANSLATED[old]
    _TRANSLATED[key] = _TRANSLATED.get(key, 0) + 1
    translation = await enrich.translate(cfg, text)
    _TRANSLATIONS[text] = translation
    if len(_TRANSLATIONS) > _TRANSLATIONS_MAX:
        _TRANSLATIONS.popitem(last=False)
    return translation


def _others(
    word: asyncpg.Record, senses: list[asyncpg.Record], parts: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Другие части речи той же леммы: уже известные словарю — с переводом,
    возможные по форме — без него (перевод появится, когда их выберут)."""
    known = {s["pos"]: s["translation"] for s in senses if not s["banned"]}
    possible = parts + lexicon.parts(word["lemma"], word["lemma"])
    order = list(dict.fromkeys([*known, *possible]))
    return [
        {"pos": pos, "translation": known.get(pos)}
        for pos in order
        if pos != word["pos"] and (pos in known or pos in lexicon.POS_UPOS)
    ]


async def _items(
    pool: asyncpg.Pool, cfg: Settings, user_id: int, text: str, pos: str | None, as_is: bool
) -> list[Item]:
    """Что добавить. Предложение целиком не учим — только устойчивые фразы из него."""
    if pos is not None:
        return [await _chosen(pool, text, pos)]

    # Готовое слово или фраза из общего словаря берутся как есть: составители
    # учебных списков считают interesting и evening самостоятельными словами,
    # а lemminflect свёл бы их к interest и even. И «a lot» — фраза, а не lot.
    async with pool.acquire() as conn:
        if await repo.get_word(conn, text) is not None:
            return [Item(text, parts=lexicon.parts(text, text))]

    marked = MARKED_RE.match(text)
    if marked and lexicon.is_word(marked[2]):
        pos = MARKED_POS[marked[1]]
        return [await _chosen(pool, lexicon.lemma_as(marked[2], pos), pos)]

    if " " not in text:
        if not lexicon.is_word(text):
            raise Rejected(f"Не знаю английского слова «{text}».")
        suggestion = None if as_is else lexicon.suggest(text)
        if suggestion:
            raise Misspelled(text, suggestion)
        analysis = lexicon.analyze(text)
        only = analysis.parts[0] if len(analysis.parts) == 1 else None
        # Форма говорит о части речи, только если это не сама лемма: booked —
        # точно глагол, а please lemminflect знает лишь глаголом, хотя в
        # словаре оно междометие — исходную форму доверяем словарю.
        return [Item(analysis.lemma, only, strict=only is not None and analysis.lemma != text,
                     analysis=analysis, parts=analysis.parts)]

    await _spend_llm(pool, cfg, user_id)
    phrases = await enrich.find_phrases(cfg, text)
    if not phrases:
        raise Rejected("Устойчивых фраз здесь нет. Отдельное слово пришли одно.")
    return [Item(phrase) for phrase in phrases]


async def _chosen(pool: asyncpg.Pool, lemma: str, pos: str) -> Item:
    """Часть речи, которую пользователь выбрал сам. Бывает ли слово такой
    частью речи, решают словарь и lemminflect, а не модель: «to apple»
    иначе стоил бы запроса к ИИ и кончился бы «ИИ не отвечает»."""
    possible = lexicon.parts(lemma, lemma)
    async with pool.acquire() as conn:
        known = {s["pos"] for s in await repo.get_senses(conn, lemma)}
    if pos not in known and pos not in possible:
        raise Rejected(f"Не знаю «{lemma}» как {POS_NAMES.get(pos, pos)}.")
    return Item(lemma, pos, strict=True, parts=possible)


def _pick(item: Item, senses: list[asyncpg.Record]) -> asyncpg.Record | None:
    """Подходящее значение из уже известных словарю. None — нужно новое."""
    if item.pos is not None:
        exact = [s for s in senses if s["pos"] == item.pos]
        if exact or item.strict:
            return exact[0] if exact else None
    fitting = [s for s in senses if s["pos"] in item.parts]
    # books: и noun, и verb подходят — берём основное значение из подходящих.
    # Ничего не подошло (please — interjection, а lemminflect думает verb) —
    # всё равно основное: словарь знает слово лучше разбора формы.
    return (fitting or senses or [None])[0]


async def _ensure_word(
    pool: asyncpg.Pool, cfg: Settings, user_id: int, item: Item
) -> asyncpg.Record:
    async with pool.acquire() as conn:
        senses = await repo.get_senses(conn, item.lemma)
    if any(s["banned"] for s in senses):
        raise Rejected(f"«{item.lemma}» в словарь не добавляется.")
    word = _pick(item, senses)
    if word is not None:
        return word

    await _spend_llm(pool, cfg, user_id)
    # Часть речи модели называется, только если она точно известна: иначе
    # please попросили бы глаголом, а основное значение пусть выберет модель.
    try:
        fields = await enrich.fetch_word(cfg, item.lemma, item.pos if item.strict else None)
    except enrich.EnrichError:
        # Часть речи вывели из формы, а модель о ней карточку не дала: лучше
        # показать основное значение, чем «ИИ не отвечает». Выбранную явно
        # (кнопкой, «to book») так не подменяем — там у такого ответа нет смысла.
        if senses and item.analysis is not None:
            return senses[0]
        raise
    # Частоты фраз wordfreq не знает и выдумывает их из отдельных слов
    # («up give» = «give up»), поэтому для фразы верим оценке модели.
    zipf = fields["zipf"] if " " in item.lemma else lexicon.lemma_zipf(item.lemma)
    async with pool.acquire() as conn:
        return await repo.save_word(conn, item.lemma, zipf, fields)


async def backfill_zipf(pool: asyncpg.Pool) -> None:
    """Частота для слов, перенесённых из личных карточек миграцией 002:
    в SQL её не посчитать, а с нулём они навсегда ушли бы в конец выдачи.
    После первого запуска список пуст, и это один быстрый select."""
    async with pool.acquire() as conn:
        for lemma in await repo.words_without_zipf(conn):
            await repo.set_zipf(conn, lemma, lexicon.lemma_zipf(lemma))


async def _spend_llm(pool: asyncpg.Pool, cfg: Settings, user_id: int) -> None:
    async with pool.acquire() as conn:
        used = await repo.spend_llm(conn, user_id, cfg.tz)
    if used > cfg.llm_daily_limit:
        raise Rejected("На сегодня лимит новых слов исчерпан. Приходи завтра.")
