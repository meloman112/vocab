"""Тесты учителя без базы: разбор вопросов, проверка ответов, текст из .docx.

Вопрос учитель пишет одной строкой: She [doesn't like] coffee. (not like) —
в квадратных скобках ответ, другие верные ответы через «|», в круглых
сразу после пропуска — подсказка ученику.
"""

import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree

GAP = re.compile(r"\[([^\[\]]*)\](?:\s*\(([^()]*)\))?")
# «1. », «2) » в начале строки: учителя вставляют нумерованные списки.
NUMBER = re.compile(r"^\s*\d{1,3}\s*[.)]\s+")

MAX_QUESTIONS = 100
MAX_LINE = 500

Part = str | dict[str, Any]


class QuestionError(ValueError):
    """Строку нельзя превратить в вопрос. Текст — для учителя."""


def parse_line(line: str) -> list[Part]:
    """Строка учителя → части: текст и пропуски {answers, hint}."""
    if len(line) > MAX_LINE:
        raise QuestionError(f"длиннее {MAX_LINE} знаков")
    parts: list[Part] = []
    pos = 0
    for m in GAP.finditer(line):
        answers = [a.strip() for a in m[1].split("|") if a.strip()]
        if not answers:
            raise QuestionError("пустые квадратные скобки: впиши в них ответ")
        parts.append(line[pos:m.start()])
        parts.append({"answers": answers, "hint": (m[2] or "").strip()})
        pos = m.end()
    parts.append(line[pos:])
    rest = "".join(p for p in parts if isinstance(p, str))
    if "[" in rest or "]" in rest:
        raise QuestionError("скобка [ или ] без пары")
    if len(parts) == 1:
        raise QuestionError("нет пропуска: ответ пишется в квадратных скобках, [doesn't like]")
    return [p for p in parts if p != ""]


def parse_text(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Весь текст учителя: вопрос на строку. Возвращает вопросы и ошибки
    с номерами строк — учитель правит их, а не угадывает."""
    questions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = NUMBER.sub("", raw).strip()
        if not line:
            continue
        try:
            questions.append({"parts": parse_line(line)})
        except QuestionError as exc:
            errors.append({"line": n, "error": str(exc)})
    if len(questions) > MAX_QUESTIONS:
        errors.append({"line": 0, "error": f"больше {MAX_QUESTIONS} вопросов"})
    return questions, errors


def gaps(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Пропуски всех вопросов подряд: ответы ученика лежат в том же порядке."""
    return [p for q in questions for p in q["parts"] if isinstance(p, dict)]


def hide_answers(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"parts": [p if isinstance(p, str) else {"hint": p["hint"]} for p in q["parts"]]}
        for q in questions
    ]


_CONTRACTIONS = [
    (r"\bi'm\b", "i am"), (r"'re\b", " are"), (r"'ve\b", " have"), (r"'ll\b", " will"),
    (r"\bwon't\b", "will not"), (r"\bcan't\b", "can not"), (r"\bcannot\b", "can not"),
    (r"\bshan't\b", "shall not"), (r"n't\b", " not"),
    (r"\b(travel|cancel|label|model|signal|quarrel|level|fuel)l(ed|ing)\b", r"\1\2"),
    (r"\b(real|recogn|apolog|organ|critic|summar|emphas|memor|special|practi)is(e|es|ed|ing)\b", r"\1iz\2"),
    (r"\bpractis", "practic"), (r"\bcentre\b", "center"), (r"\bcolour", "color"),
]


def norm(s: str) -> str:
    """Как norm() тетради (miniapp engine.ts): don't и do not — один ответ,
    регистр и пунктуация не важны. 's и 'd не раскрываются: is или has,
    would или had — правило не угадает."""
    t = s.lower().replace("’", "'").replace("`", "'").replace("‘", "'")
    t = re.sub(r"[?.!—–;:\"“”«»()…_,]", " ", t)
    for pattern, repl in _CONTRACTIONS:
        t = re.sub(pattern, repl, t)
    return " ".join(t.split())


def marks(questions: list[dict[str, Any]], answers: list[str],
          accepted: dict[int, set[str]]) -> list[bool]:
    """Верен ли каждый пропуск. accepted — засчитанные учителем, уже в norm."""
    result = []
    for i, gap in enumerate(gaps(questions)):
        given = norm(answers[i]) if i < len(answers) else ""
        ok = {norm(a) for a in gap["answers"]} | accepted.get(i, set())
        result.append(bool(given) and given in ok)
    return result


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(data: bytes) -> str:
    """Текст .docx по абзацам. Своя распаковка: docx — zip с XML, и ради
    одного document.xml зависимость не нужна."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise QuestionError("это не файл Word (.docx)") from exc
    lines = []
    for p in root.iter(f"{W}p"):
        text = "".join(
            (node.text or "") if node.tag == f"{W}t" else "\t" if node.tag == f"{W}tab" else ""
            for node in p.iter()
        )
        lines.append(text)
    return "\n".join(lines).strip()
