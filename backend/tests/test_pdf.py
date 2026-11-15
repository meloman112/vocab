from vocab.grammar import pdf


def test_render_survives_markup_and_gaps():
    # Ввод ученика с разметкой Typst, перенос строки, пустой ответ, пропуск без подсказки.
    ex = [{"id": 7, "task": "Fill in #1 *now*.", "items": [
        {"n": 1, "done": True, "parts": [{"text": "I\n"}, {"answer": "#am* [x] $y$"}, {"text": " ok"}]},
        {"n": 2, "done": False, "parts": [{"text": "He "}, {"answer": ""}, {"hint": None}, {"hint": "(be)"}]},
    ]}]
    out = pdf.render("Ann #bold", ex, {"done": 0, "clean": 0, "errors": []})
    assert out.startswith(b"%PDF")


def _exercises():
    return [{"id": 15, "task": "Fill.", "items": [
        {"n": 1, "done": True, "parts": [{"text": "I "}, {"answer": "went"}]},
        {"n": 3, "done": True, "parts": [{"answer": "was"}, {"text": " and "}, {"answer": "saw"}]},
        {"n": 4, "done": False, "parts": [{"answer": "x"}]},
    ]}]


def test_annotate_marks_wrong_answers_and_counts():
    wrong = {("15-2", 1): ("seen", "Не то время. «yesterday» — прошедшее."),
             ("15-3", 0): ("y", "Опечатка.")}  # n=4 не сделано — не учитывается
    ex = _exercises()
    summary = pdf.annotate(ex, wrong)
    assert summary == {"done": 2, "clean": 1, "errors": [{"kind": "Не то время", "count": 1}]}
    assert "wrong" not in ex[0]["items"][0]["parts"][1]
    assert "wrong" not in ex[0]["items"][1]["parts"][0]
    assert ex[0]["items"][1]["parts"][2]["wrong"] == "seen"
    assert "wrong" not in ex[0]["items"][2]["parts"][0]


def test_annotate_limits_error_kinds_to_five_by_count():
    wrong = {(f"1-{i}", 0): ("a", f"Тип{i}. x") for i in range(7)}
    wrong[("1-0", 1)] = ("b", "Тип6. y")
    ex = [{"id": 1, "task": "", "items": [
        {"n": i + 1, "done": True, "parts": [{"answer": "a"}, {"answer": "b"}]} for i in range(7)]}]
    errors = pdf.annotate(ex, wrong)["errors"]
    assert len(errors) == 5 and errors[0] == {"kind": "Тип6", "count": 2}


def test_render_with_mistakes_and_summary():
    ex = _exercises()
    summary = pdf.annotate(ex, {("15-2", 1): ("#seen*", "Опечатка. x")})
    assert pdf.render("Ann", ex, summary).startswith(b"%PDF")
