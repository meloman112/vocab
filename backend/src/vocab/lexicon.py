"""Разбор словоформы офлайн: лемма, грамматическая форма, частотность.

Ни модели, ни сети: lemminflect — словарь словоформ с правилами для
незнакомых слов, wordfreq — частоты по большому корпусу. Ответ за
миллисекунды, поэтому ИИ зовётся только за переводом новой леммы.
"""

import re
from dataclasses import dataclass

from lemminflect import getAllInflections, getAllLemmas
from wordfreq import zipf_frequency

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


def zipf(text: str) -> float:
    """Частота по шкале Zipf: 7 — the, 5 — read, 3 — redundant, 0 — нет такого."""
    return zipf_frequency(text, "en")


def is_word(text: str) -> bool:
    return bool(WORD_RE.match(text)) and zipf(text) > 0
