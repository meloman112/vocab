"""PDF с решёнными упражнениями: текст задания, ответы ученика выделены.
Вёрстка — в workbook.typ, здесь только вызов Typst (~15 мс против ~100 у ReportLab)."""

import json
from collections import Counter
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import typst

# DejaVu — ради кириллицы. Ставится в образ пакетом fonts-dejavu-core; без него
# (локально) Typst берёт встроенный шрифт, а не падает.
FONTS = "/usr/share/fonts/truetype/dejavu"
TEMPLATE = Path(__file__).with_name("workbook.typ").read_bytes()


@lru_cache
def _fonts() -> typst.Fonts:
    # Системные шрифты не сканируем: долго, и вид PDF зависел бы от машины.
    return typst.Fonts(include_system_fonts=False, font_paths=[FONTS])


def warm() -> None:
    """Сканирование шрифтов при старте API, а не на первом PDF ученика."""
    _fonts()


MAX_ERROR_KINDS = 5


def item_key(exercise_id: int, n: int) -> str:
    """Ключ задания в базе: номер упражнения и индекс задания с нуля."""
    return f"{exercise_id}-{n - 1}"


def annotate(
    exercises: list[dict[str, Any]], wrong: dict[tuple[str, int], tuple[str, str]]
) -> dict[str, Any]:
    """Дописывает частям с ответом `wrong` — первый неверный ответ — и считает
    сводку. Пропуски идут по порядку частей с answer, как slot в базе."""
    done = clean = 0
    kinds: Counter[str] = Counter()
    for ex in exercises:
        for item in ex["items"]:
            if not item["done"]:
                continue
            key = item_key(ex["id"], item["n"])
            slots = [p for p in item["parts"] if p.get("answer") is not None]
            found = []
            for slot, part in enumerate(slots):
                if (key, slot) in wrong:
                    part["wrong"], why = wrong[key, slot]
                    found.append(why)
            done += 1
            clean += not found
            # Тип ошибки — текст разбора до первой точки.
            kinds.update(why.split(".")[0].strip() or "Ошибка" for why in found)
    errors = [{"kind": k, "count": c} for k, c in kinds.most_common(MAX_ERROR_KINDS)]
    return {"done": done, "clean": clean, "errors": errors}


def render(student: str, exercises: list[dict[str, Any]], summary: dict[str, Any]) -> bytes:
    data = {"student": student, "date": f"{date.today():%d.%m.%Y}",
            "exercises": exercises, "summary": summary}
    # Компилятор на каждый вызов: render идёт из пула потоков, а общий
    # экземпляр между потоками делить незачем — создание стоит доли мс.
    return typst.Compiler(TEMPLATE, font_paths=_fonts()).compile(sys_inputs={"data": json.dumps(data)})
