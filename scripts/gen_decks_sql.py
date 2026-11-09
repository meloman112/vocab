"""Генерирует migrations/009_decks.sql из файлов учителя (xlsx «Словарь 3000», docx «Глаголы и
прилагательные с предлогами») и выгрузки lemma/pos боевого словаря (lemmapos.tsv).
Запуск: uv run --with openpyxl --with python-docx python scripts/gen_decks_sql.py <dir> <out.sql>."""
import sys, re, json, collections, openpyxl, docx
from docx.table import Table
from docx.text.paragraph import Paragraph

d, out = sys.argv[1], sys.argv[2]
SHEETS = {"Глаголы": "verb", "Существительные": "noun", "Прилагательные": "adjective",
          "Наречия": "adverb", "Предлоги": "preposition", "Союз": "conjunction"}
CORE, PREP = "B1 3000 words", "Глаголы и прилагательные с предлогами"
IRREGULAR_PLURAL = {"children": "child"}

def clean(x):
    return re.sub(r"\s+", " ", str(x or "").replace("\xa0", " ").replace("’", "'")).strip()

def split_paren(s):
    m = re.match(r"^(.*?)\s*\((.*)\)$", s)
    return (m.group(1), m.group(2)) if m else (s, "")

db = collections.defaultdict(set)
for line in open(f"{d}/lemmapos.tsv"):
    lemma, pos = line.rstrip("\n").split("\t")
    db[lemma].add(pos)

def singular(lemma, pos):
    """Множественное из файла привязываем к единственному из словаря."""
    if pos != "noun" or pos in db.get(lemma, ()):
        return lemma
    if lemma in IRREGULAR_PLURAL:
        return IRREGULAR_PLURAL[lemma]
    for cut, add in (("ies", "y"), ("es", ""), ("s", "")):
        if lemma.endswith(cut) and "noun" in db.get(lemma[: -len(cut)] + add, ()):
            return lemma[: -len(cut)] + add
    return lemma

rows = []
wb = openpyxl.load_workbook(f"{d}/slovar3000.xlsx", read_only=True)
for ws in wb.worksheets:
    pos, topic = SHEETS[ws.title], None
    for r in ws.iter_rows(values_only=True):
        if r[0] and not r[1]:
            topic = clean(r[0]); continue
        if not r[0] or not r[1]:
            continue
        en, ipa, ru = clean(r[0]), clean(r[1]), clean(r[2])
        if en.startswith("("):  # «(one year) ago»
            en = en.split(")", 1)[1].strip() + " (" + en[1:].split(")", 1)[0] + ")"
        head, paren = split_paren(en)
        ru_head, ru_paren = split_paren(ru)
        lemmas = [x.strip().lower() for x in head.split(",") if x.strip()]
        ipas = [x.strip(" ,") for x in re.split(r"\]\s*,?\s*\[", ipa.strip(" []"))]
        # Транскрипция в файле иногда склеена с текстом («fiancé[iː») — такая хуже пустой.
        ipas = ["" if re.search(r"[\[\],]|fianc", x) else x for x in ipas]
        forms, irregular, examples = "", False, []
        if pos == "verb" and paren and "," in paren:
            forms = " · ".join([head.lower(), *[p.strip() for p in paren.split(",")]])
            irregular = True
        if pos in ("preposition", "conjunction") and paren:
            examples = [{"en": paren, "ru": ru_paren}]
        for i, lemma in enumerate(lemmas):
            rows.append(dict(lemma=singular(lemma, pos), pos=pos, translation=ru_head,
                             ipa=ipas[i] if len(ipas) == len(lemmas) else "",
                             forms=forms if len(lemmas) == 1 else "", irregular=irregular,
                             examples=examples, deck=CORE, topic=topic))

doc = docx.Document(f"{d}/verbs_prep.docx")
topic = None
for el in doc.element.body.iterchildren():
    tag = el.tag.split("}")[1]
    if tag == "p":
        t = Paragraph(el, doc).text.strip()
        m = re.match(r"^(?:\d+\.|Часть \d+\.)\s*(.+)$", t)
        if m: topic = m.group(1)
    elif tag == "tbl":
        for row in Table(el, doc).rows[1:]:
            combo, ru, example = (clean(c.text) for c in row.cells)
            ex_en, _, ex_ru = example.partition(" — ")
            rows.append(dict(lemma=combo.lower(), pos="phrase", translation=ru, ipa="",
                             forms="", irregular=False,
                             examples=[{"en": ex_en, "ru": ex_ru}], deck=PREP, topic=topic))

def q(s):
    return "'" + str(s).replace("'", "''") + "'"

values = ",\n".join(
    f"({n}, {q(r['lemma'])}, {q(r['pos'])}, {q(r['translation'])}, {q(r['ipa'])}, "
    f"{q(r['forms'])}, {str(r['irregular']).lower()}, {q(json.dumps(r['examples'], ensure_ascii=False))}, "
    f"{q(r['deck'])}, {q(r['topic'])})"
    for n, r in enumerate(rows, 1))

open(out, "w").write(f"""-- Наборы слов от учителя: «B1 3000 words» (Словарь 3000 v2.9.xlsx) и
-- «Глаголы и прилагательные с предлогами» (docx). Отдельных наборов нет —
-- это классификация общего словаря: deck и topic для метки на карточке,
-- deck_order — порядок файла, в нём «Учить новые» выдаёт слова первыми.
--
-- Слово ищется по (lemma, pos): «end» из листа глаголов — «заканчивать»,
-- а не существительное «конец», поэтому привязать его к существующему
-- существительному значит учить не то значение. Нет нужной части речи —
-- заводится новое слово с переводом и транскрипцией из файла; примеры
-- к таким словам дописывает модель (python -m vocab.fill_examples).
-- Сгенерировано скриптом из файлов; содержимое существующих слов не меняется.

alter table words
  add column deck       text,
  add column deck_order int,
  add column topic      text;

create temp table deck_import (
  n int, lemma text, pos text, translation text, ipa text, forms text,
  irregular boolean, examples jsonb, deck text, topic text
) on commit drop;

insert into deck_import values
{values};

-- Глагол из файла, который в словаре есть только как modal (can) или как
-- фраза (give up), — то же слово, а не новое.
update deck_import i set pos = w.pos
from words w
where w.lemma = i.lemma and i.pos = 'verb' and w.pos in ('modal', 'phrase')
  and not exists (select 1 from words x where x.lemma = i.lemma and x.pos = 'verb');

-- Слово встречается в файле несколько раз (run в двух темах) — берётся
-- первое вхождение.
create temp table deck_first on commit drop as
select distinct on (lemma, pos) * from deck_import order by lemma, pos, n;

insert into words (lemma, translation, ipa, pos, forms, irregular, examples)
select lemma, translation, ipa, pos, forms, irregular, examples from deck_first
on conflict (lemma, pos) do nothing;

update words w set deck = f.deck, deck_order = f.n, topic = f.topic
from deck_first f
where w.lemma = f.lemma and w.pos = f.pos;
""")
print(len(rows), "rows")
