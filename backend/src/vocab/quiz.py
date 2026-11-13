"""Материал для тестов: варианты ответа и пропуск в примере.

Собирается на сервере, а не в клиентах: мини-апп и бот (quiz-опросы)
получают одни и те же варианты, и правило «большой» ≠ «крупный» живёт
в одном месте.
"""

import random
import re
from collections.abc import Mapping, Sequence
from typing import Any

from lemminflect import getAllInflections

CHOICES = 4
BLANK = "_____"


def meanings(translation: str) -> set[str]:
    """«книга, том; издание» → {книга, том, издание}."""
    return {m.strip().lower() for m in re.split(r"[,;]", translation) if m.strip()}


def spread(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Тот же порядок, но слова с общим переводом не идут подряд:
    postpone и put off («откладывать») рядом путаются и учатся хуже."""
    rest, out = list(rows), []
    while rest:
        last = meanings(out[-1]["translation"]) if out else set()
        pick = next((r for r in rest if not meanings(r["translation"]) & last), rest[0])
        rest.remove(pick)
        out.append(pick)
    return out


def choices(
    card: Mapping[str, Any], pool: Sequence[Mapping[str, Any]], field: str, rng: random.Random
) -> list[str]:
    """Правильный ответ и до трёх неправильных, перемешанные.

    field — что показывать: translation (EN→RU) или lemma (RU→EN). Сначала
    берутся слова той же части речи: глагол среди существительных угадывается
    по форме. Синоним с общим значением в варианты не попадает — иначе
    правильных ответов два.
    """
    correct = card["translation"] if field == "translation" else card["word"]
    taken = meanings(card["translation"])
    picked: list[str] = []
    same_pos = [w for w in pool if w["pos"] == card["pos"]]
    other_pos = [w for w in pool if w["pos"] != card["pos"]]
    for word in same_pos + other_pos:
        option = word[field]
        if word["lemma"] == card["word"] or option == correct or option in picked:
            continue
        if taken & meanings(word["translation"]):
            continue
        picked.append(option)
        if len(picked) == CHOICES - 1:
            break
    options = [correct, *picked]
    rng.shuffle(options)
    return options


def forms_of(lemma: str, forms: str) -> set[str]:
    """Все формы леммы: go → goes, going, went, gone. forms из словаря
    («learn · learned/learnt · learned/learnt») добавляет то, чего не знает
    lemminflect."""
    found = {lemma}
    for by_tag in getAllInflections(lemma).values():
        found.update(by_tag)
    for part in re.split(r"[·/]", forms):
        if part.strip():
            found.add(part.strip().lower())
    return found


def cloze(lemma: str, forms: str, examples: Sequence[Mapping[str, str]]) -> dict[str, str] | None:
    """Первый пример, где встречается форма слова, — с пропуском на её месте.

    Для фразы склоняется первое слово: give up → gave up. answer — то, что
    стоит в предложении (went), а не лемма: проверяется знание формы.
    """
    head, _, tail = lemma.partition(" ")
    variants = sorted(forms_of(head, "" if tail else forms), key=len, reverse=True)
    tail_re = r"\s+" + r"\s+".join(map(re.escape, tail.split())) if tail else ""
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(v) + tail_re for v in variants) + r")\b", re.IGNORECASE
    )
    for example in examples:
        match = pattern.search(example["en"])
        if match:
            text = example["en"][: match.start()] + BLANK + example["en"][match.end():]
            return {"text": text, "answer": match.group(1).lower(), "ru": example["ru"]}
    return None
