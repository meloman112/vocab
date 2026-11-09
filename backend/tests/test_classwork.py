import io
import zipfile

import pytest

from vocab import classwork
from vocab.enrich import parse_test


def test_line_with_gap_and_hint():
    assert classwork.parse_line("She [doesn't like] (not like) coffee.") == [
        "She ", {"answers": ["doesn't like"], "hint": "not like"}, " coffee.",
    ]


def test_several_answers_and_gaps():
    parts = classwork.parse_line("[Did you see|Have you seen] it? I [saw] it.")
    assert parts[0] == {"answers": ["Did you see", "Have you seen"], "hint": ""}
    assert len(classwork.gaps([{"parts": parts}])) == 2


@pytest.mark.parametrize("line", ["No gap here.", "Empty [] gap.", "Broken [gap.", "Stray ] [ok]"])
def test_bad_lines(line):
    with pytest.raises(classwork.QuestionError):
        classwork.parse_line(line)


def test_text_skips_numbers_and_blank_lines_and_reports_line():
    questions, errors = classwork.parse_text("1. I [am] here.\n\n2) No gap\n3. We [are].")
    assert len(questions) == 2
    assert questions[0]["parts"][0] == "I "
    assert errors == [{"line": 3, "error": errors[0]["error"]}]


@pytest.mark.parametrize("given", ["does not like", "DOESN'T LIKE", "doesn’t  like.", "doesn't like"])
def test_contractions_count(given):
    q = [{"parts": [{"answers": ["doesn't like"], "hint": ""}]}]
    assert classwork.marks(q, [given], {}) == [True]


def test_will_not_and_have():
    q = [{"parts": [{"answers": ["won't come"], "hint": ""}, " ", {"answers": ["I have lived"], "hint": ""}]}]
    assert classwork.marks(q, ["will not come", "I've lived"], {}) == [True, True]


def test_s_is_not_expanded():
    q = [{"parts": [{"answers": ["he has gone"], "hint": ""}]}]
    assert classwork.marks(q, ["he's gone"], {}) == [False]


def test_empty_and_accepted():
    q = [{"parts": [{"answers": ["were"], "hint": ""}]}]
    assert classwork.marks(q, [""], {}) == [False]
    assert classwork.marks(q, ["Was"], {0: {classwork.norm("was")}}) == [True]


def test_hide_answers():
    q = [{"parts": ["I ", {"answers": ["am"], "hint": "be"}]}]
    assert classwork.hide_answers(q) == [{"parts": ["I ", {"hint": "be"}]}]


def test_docx_text():
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        "<w:p><w:r><w:t>1. She (not like)</w:t></w:r><w:r><w:t xml:space=\"preserve\"> coffee.</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>2. Look!</w:t></w:r></w:p></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    assert classwork.docx_text(buf.getvalue()) == "1. She (not like) coffee.\n2. Look!"
    with pytest.raises(classwork.QuestionError):
        classwork.docx_text(b"not a zip")


def test_parse_ai_answer():
    rows = parse_test('{"questions": [{"line": "I [am]  here.", "guessed": true, "note": "проверь"}, {"line": ""}]}')
    assert rows == [{"line": "I [am] here.", "guessed": True, "note": "проверь"}]
