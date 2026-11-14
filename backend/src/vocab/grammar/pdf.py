"""PDF с решёнными упражнениями: текст задания, ответы ученика выделены.
Вёрстка — в workbook.typ, здесь только вызов Typst (~15 мс против ~100 у ReportLab)."""

import json
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


def render(student: str, exercises: list[dict[str, Any]]) -> bytes:
    data = {"student": student, "date": f"{date.today():%d.%m.%Y}", "exercises": exercises}
    # Компилятор на каждый вызов: render идёт из пула потоков, а общий
    # экземпляр между потоками делить незачем — создание стоит доли мс.
    return typst.Compiler(TEMPLATE, font_paths=_fonts()).compile(sys_inputs={"data": json.dumps(data)})
