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


@dataclass(frozen=True)
class Analysis:
    lemma: str
    # None — прислана сама лемма, объяснять нечего.
    form_note: str | None


def analyze(word: str) -> Analysis:
    """went → go (V2), children → child (мн. ч.), go → go."""
    lemmas = getAllLemmas(word)
    for upos in UPOS_ORDER:
        for lemma in lemmas.get(upos, ()):
            if lemma != word:
                return Analysis(lemma, _form_note(word, lemma, upos))
    return Analysis(word, None)


def _form_note(word: str, lemma: str, upos: str) -> str | None:
    # read → read · read: одна форма бывает и V2, и V3, отсюда список.
    notes = [
        TAG_NOTES[tag]
        for tag, forms in getAllInflections(lemma, upos=upos).items()
        if word in forms and tag in TAG_NOTES
    ]
    return " / ".join(dict.fromkeys(notes)) or None


def lemma_zipf(lemma: str) -> float:
    """Частота леммы вместе со всеми формами по шкале Zipf.

    Одна только «go» дала бы 6.03, а с went, gone, going, goes — 6.41:
    без суммы слова с неправильными формами занижены.
    """
    forms = {lemma} | {f for by_tag in getAllInflections(lemma).values() for f in by_tag}
    total = sum(word_frequency(form, "en") for form in forms)
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


def rank_label(zipf: float) -> str:
    place = rank(zipf)
    for top in TOP_STEPS:
        if place <= top:
            return f"топ-{top}"
    return f"реже топ-{TOP_STEPS[-1]}"


def is_word(text: str) -> bool:
    return bool(WORD_RE.match(text)) and zipf_frequency(text, "en") > 0
