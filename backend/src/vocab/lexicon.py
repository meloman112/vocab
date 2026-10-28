"""Разбор словоформы офлайн: лемма, грамматическая форма, частотность.

Ни модели, ни сети: lemminflect — словарь словоформ с правилами для
незнакомых слов, wordfreq — частоты по большому корпусу. Ответ за
миллисекунды, поэтому ИИ зовётся только за переводом новой леммы.
"""

import bisect
import math
import re
from dataclasses import dataclass
from functools import lru_cache

from lemminflect import getAllInflections, getAllLemmas
from wordfreq import top_n_list, word_frequency, zipf_frequency

WORD_RE = re.compile(r"^[a-z][a-z'-]*$")

# Глагол первым: reading → read полезнее, чем reading как «чтение», а
# saw → see чаще, чем «пила». Второе значение пользователь пришлёт сам.
UPOS_ORDER = ("VERB", "NOUN", "ADJ", "ADV")

# Метки Penn Treebank, которые отдаёт lemminflect. Базовые формы (VB, NN,
# JJ) сюда не входят: «это начальная форма» пользователю ничего не говорит.
TAG_NOTES = {
    "VBD": "прошедшее время (V2)",
    "VBN": "третья форма, причастие прошедшего времени (V3)",
    "VBG": "форма на -ing: Continuous или герундий",
    "VBZ": "настоящее время для he/she/it",
    "NNS": "множественное число",
    "JJR": "сравнительная степень",
    "RBR": "сравнительная степень",
    "JJS": "превосходная степень",
    "RBS": "превосходная степень",
}


# Из стольких самых частых словоформ строится рейтинг лемм: выходит
# ~45 тысяч лемм, дальше начинается шум из имён и опечаток.
RANKED_FORMS = 60_000
TOP_STEPS = (100, 500, 1000, 2000, 5000, 10000, 20000)


# Часть речи карточки в общем словаре → метка lemminflect.
POS_UPOS = {"noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adverb": "ADV"}


@dataclass(frozen=True)
class Analysis:
    lemma: str
    # Пары (часть речи, пометка). Пусто — прислана сама лемма, объяснять нечего.
    notes: tuple[tuple[str, str], ...] = ()

    @property
    def form_note(self) -> str | None:
        """Все прочтения формы: books — и «книги», и «бронирует»."""
        return " / ".join(dict.fromkeys(note for _, note in self.notes)) or None

    def note_for(self, pos: str | None) -> str | None:
        """Пометка для карточки с этой частью речи.

        Карточка показывает одно значение: bicycle — noun, «велосипед».
        Пометка «he/she/it» рядом с существительным сбивает с толку того,
        кто проверить её не может, поэтому берутся только прочтения той же
        части речи. Не совпало ни одно (фраза, модальный глагол) — все.
        """
        upos = POS_UPOS.get(pos or "")
        same = tuple(n for n in self.notes if n[0] == upos)
        return Analysis(self.lemma, same or self.notes).form_note


def analyze(word: str) -> Analysis:
    """went → go (V2), children → child (мн. ч.), go → go."""
    lemmas = getAllLemmas(word)
    # Правила lemminflect порождают и редкие ложные леммы: number → numb
    # («онемевший» в сравнительной степени), data → datum, overcome →
    # over-come. Настоящая лемма не бывает намного реже своей формы; дефис
    # проверяется отдельно — wordfreq считает over-come как over и come.
    floor = zipf_frequency(word, "en") - 1
    for upos in UPOS_ORDER:
        for lemma in lemmas.get(upos, ()):
            if lemma == word or ("-" in lemma and "-" not in word):
                continue
            if zipf_frequency(lemma, "en") >= floor:
                return Analysis(lemma, _form_notes(word, lemma, lemmas))
    return Analysis(word)


# Для пометок существительное первым: bicycles без контекста — скорее
# «велосипеды», чем «он ездит на велосипеде».
NOTE_ORDER = ("NOUN", "VERB", "ADJ", "ADV")


def _form_notes(
    word: str, lemma: str, lemmas: dict[str, tuple[str, ...]]
) -> tuple[tuple[str, str], ...]:
    # Пометки со всех частей речи, где у слова та же лемма: books — и
    # «книги», и «бронирует»; read → read · read — и V2, и V3.
    notes = [
        (upos, TAG_NOTES[tag])
        for upos in NOTE_ORDER
        if lemma in lemmas.get(upos, ())
        for tag, forms in getAllInflections(lemma, upos=upos).items()
        if word in forms and tag in TAG_NOTES
    ]
    return tuple(dict.fromkeys(notes))


def lemma_zipf(lemma: str) -> float:
    """Частота леммы вместе со всеми формами по шкале Zipf.

    Одна только «go» дала бы 6.03, а с went, gone, going, goes — 6.41:
    без суммы слова с неправильными формами занижены.

    Считаются только формы, которые сами сводятся к этой лемме: иначе numb
    забрал бы частоту number, а being — частоту being от be.
    """
    forms = {lemma} | {f for by_tag in getAllInflections(lemma).values() for f in by_tag}
    total = sum(word_frequency(form, "en") for form in forms if analyze(form).lemma == lemma)
    # Zipf — log10 от числа употреблений на миллиард слов.
    return round(math.log10(total) + 9, 2) if total else 0.0


@lru_cache
def _ranked_zipfs() -> list[float]:
    """Частоты лемм по возрастанию — шкала, на которой ищется место слова.

    Строится ~2 секунды один раз на процесс; API делает это при старте,
    чтобы не заставить ждать первого пользователя.
    """
    lemmas = {analyze(w).lemma for w in top_n_list("en", RANKED_FORMS) if WORD_RE.match(w)}
    return sorted(lemma_zipf(lemma) for lemma in lemmas)


def rank(zipf: float) -> int:
    """Место по частоте среди лемм: the — 1, go — 45, reliable — ~3800.

    Считается по числу, а не по написанию, поэтому годится и для фраз
    с частотой от модели.
    """
    zipfs = _ranked_zipfs()
    return len(zipfs) - bisect.bisect_right(zipfs, zipf) + 1


def rank_label(zipf: float, level: str | None = None) -> str:
    """«B1 · топ-2000»: уровень — насколько слово трудное, топ — насколько частое."""
    place = rank(zipf)
    top = next((f"топ-{top}" for top in TOP_STEPS if place <= top), f"реже топ-{TOP_STEPS[-1]}")
    return f"{level} · {top}" if level else top


def is_word(text: str) -> bool:
    return bool(WORD_RE.match(text)) and zipf_frequency(text, "en") > 0
