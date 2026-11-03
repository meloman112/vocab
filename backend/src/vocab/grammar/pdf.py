"""PDF с решёнными упражнениями: текст задания, ответы ученика выделены."""

from datetime import date
from functools import lru_cache
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

# DejaVu — ради кириллицы в заголовках: встроенные шрифты PDF её не знают.
# Ставится в образ пакетом fonts-dejavu-core.
FONTS = "/usr/share/fonts/truetype/dejavu"
INK, PEN, MUTED = "#18213a", "#2346d6", "#66708a"


@lru_cache
def _styles() -> dict[str, ParagraphStyle]:
    # Регистрация при первом PDF, а не при импорте: тестам и боту шрифты не нужны.
    pdfmetrics.registerFont(TTFont("Sans", f"{FONTS}/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("Sans-Bold", f"{FONTS}/DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold")
    return {
        "title": ParagraphStyle("title", fontName="Sans-Bold", fontSize=16, leading=20, textColor=INK),
        "meta": ParagraphStyle("meta", fontName="Sans", fontSize=10, leading=14, textColor=MUTED),
        "head": ParagraphStyle("head", fontName="Sans-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=14),
        "task": ParagraphStyle("task", fontName="Sans", fontSize=10, leading=14, textColor=MUTED, spaceAfter=6),
        "item": ParagraphStyle("item", fontName="Sans", fontSize=11.5, leading=17, textColor=INK,
                               leftIndent=6 * mm, firstLineIndent=-6 * mm, spaceAfter=3),
    }


def render(student: str, exercises: list[dict[str, Any]]) -> bytes:
    s = _styles()
    story = [
        Paragraph("Work book — домашняя работа", s["title"]),
        Paragraph(escape(f"{student} · {date.today():%d.%m.%Y}"), s["meta"]),
    ]
    for ex in exercises:
        done = sum(item["done"] for item in ex["items"])
        story += [
            Paragraph(f"Упражнение {ex['id']}", s["head"]),
            Paragraph(escape(f"{ex['task']} Сделано {done} из {len(ex['items'])}."), s["task"]),
            *(Paragraph(_item(item), s["item"]) for item in ex["items"]),
        ]

    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title="Work book", leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    return buf.getvalue()


def _item(item: dict[str, Any]) -> str:
    """Предложение с ответами ученика синим и полужирным; несделанное — со скобками из книги."""
    out = [f"{item['n']}. "]
    for part in item["parts"]:
        if part.get("text") is not None:
            out.append(escape(part["text"]).replace("\n", "<br/>"))
        elif part.get("answer"):
            out.append(f'<font color="{PEN}"><b>{escape(part["answer"])}</b></font>')
        else:
            out.append(f'<font color="{MUTED}">{escape(part.get("hint") or "___")}</font>')
    return "".join(out)
