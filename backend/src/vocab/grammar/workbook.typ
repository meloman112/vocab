// PDF с решёнными упражнениями. Данные приходят JSON-ом через sys.inputs,
// а не вклейкой в разметку: ответ ученика с # или * остаётся просто текстом.
#let d = json(bytes(sys.inputs.data))
#let ink = rgb("#18213a")
#let pen = rgb("#2346d6")
#let muted = rgb("#66708a")

#set document(title: "Work book")
#set page(paper: "a4", margin: (x: 18mm, y: 16mm))
#set text(font: "DejaVu Sans", size: 11.5pt, fill: ink, lang: "ru")
#set par(leading: 0.7em, spacing: 0.55em)

#text(16pt, weight: "bold")[Work book — домашняя работа]
#parbreak()
#text(10pt, fill: muted)[#d.student · #d.date]

#for ex in d.exercises {
  block(above: 18pt, below: 6pt, text(13pt, weight: "bold")[Упражнение #ex.id])
  block(below: 8pt, text(10pt, fill: muted)[
    #ex.task Сделано #ex.items.filter(i => i.done).len() из #ex.items.len().
  ])
  for item in ex.items {
    // Отступ как в книге: номер слева, перенос строки — под текстом.
    par(hanging-indent: 6mm)[#item.n. #for p in item.parts {
      let (text: t, answer: a, hint: h) = (text: none, answer: none, hint: none) + p
      if t != none { t }
      else if a not in (none, "") { text(fill: pen, weight: "bold", a) }
      else { text(fill: muted, if h in (none, "") { "___" } else { h }) }
    }]
  }
}
