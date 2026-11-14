from vocab.grammar import pdf


def test_render_survives_markup_and_gaps():
    # Ввод ученика с разметкой Typst, перенос строки, пустой ответ, пропуск без подсказки.
    ex = [{"id": 7, "task": "Fill in #1 *now*.", "items": [
        {"n": 1, "done": True, "parts": [{"text": "I\n"}, {"answer": "#am* [x] $y$"}, {"text": " ok"}]},
        {"n": 2, "done": False, "parts": [{"text": "He "}, {"answer": ""}, {"hint": None}, {"hint": "(be)"}]},
    ]}]
    out = pdf.render("Ann #bold", ex)
    assert out.startswith(b"%PDF")
