"""Статический сайт для поиска: лендинг и страницы тем тетради → site/dist/.

Только стандартная библиотека. Ответов на страницах нет: в контенте их тоже
нет, ключ строит движок мини-аппа, а ручные ответы (=answer) сюда не попадают.
"""

import json
import os
import re
import shutil
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

# Название и домен ещё поменяются — всё, что от них зависит, собрано здесь.
SITE_URL = os.environ.get("SITE_URL", "https://example.com").rstrip("/")
BOT = os.environ.get("BOT", "workbookonlinebot")
NAME = os.environ.get("NAME", "Work book")
AUTHOR = os.environ.get("AUTHOR", "учитель Байрам")

LEVEL = "A2–B2"
BOT_URL = f"https://t.me/{BOT}"
FREE = "Бесплатно, без подписок и рекламы"
SITE = Path(__file__).parent
CONTENT = SITE.parent / "backend/src/vocab/grammar/content.json"
DIST = SITE / "dist"
# Сайт может жить не в корне домена: внутренние ссылки начинаются с пути SITE_URL.
BASE = urlsplit(SITE_URL).path
CSS = (SITE / "style.css").read_text(encoding="utf-8")
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
        "%3Crect width='16' height='16' rx='3' fill='%231b4fbf'/%3E"
        "%3Cpath d='M4 8.5l2.5 2.5L12 5' fill='none' stroke='%23fff' stroke-width='2'/%3E%3C/svg%3E")

# Тот же разбор пропуска, что SLOT в miniapp/src/features/grammar/engine.ts.
SLOT = re.compile(r"\{([^|}]*)\|([^|}]*)\|([^}]*)\}")
TOPIC_ID = re.compile(r"[a-z0-9-]+")
SAMPLE_EXERCISES = 3
SAMPLE_ITEMS = 5

# Настоящие ответы движка (diagnose) на задания тетради, не выдуманные.
CHECKS = [
    ("I ____ (to cook) pasta.", "am cook",
     "Нет формы -ing. Present Continuous = am/is/are + Ving."),
    ("Mr Brown ____ (to repair) his bike yesterday morning.", "repairs",
     "Не то время. «yesterday» — действие уже произошло и закончилось в прошлом, нужен Past Simple: V2 / did + V0."),
    ("He ____ (to write) English well.", "write",
     "Нет окончания -s. В Present Simple he/she/it получает -s/-es: writes."),
    ("She ____ (to break) her phone screen.", "has broke",
     "Нужна третья форма. После have/has/had — V3: break → broke → broken."),
]


def fail(message: str):
    raise SystemExit(f"site/build.py: {message}")


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} {few}"
    return f"{n} {many}"


def counts(exercises: list) -> str:
    items = sum(len(ex["items"]) for ex in exercises)
    return (f"{plural(len(exercises), 'упражнение', 'упражнения', 'упражнений')}, "
            f"{plural(items, 'задание', 'задания', 'заданий')}")


def href(path: str) -> str:
    return escape(BASE + path)


def topic_path(topic: dict) -> str:
    return f"/grammar/{topic['id']}/"


def rule_keys(topic: dict) -> list[str]:
    """Правила темы, как в мини-аппе, плюс свои правила упражнений (if-mix)."""
    keys = topic["rules"] + [ex["rule"] for ex in topic["exercises"] if "rule" in ex]
    return list(dict.fromkeys(keys))


def load_content() -> dict:
    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    for topic in content["topics"]:
        if not TOPIC_ID.fullmatch(topic["id"]):
            fail(f"id темы не годится для адреса: {topic['id']!r}")
        if not topic["exercises"]:
            fail(f"в теме {topic['id']} нет упражнений")
        for key in rule_keys(topic):
            if key not in content["rules"]:
                fail(f"тема {topic['id']} ссылается на неизвестное правило {key!r}")
    return content


def gap(match: re.Match) -> str:
    lead, bracket = match[1].strip(), match[2].strip()
    hint = f" ({bracket})" if bracket and bracket != "…" else ""
    return f"{lead} ____{hint}".strip()


def plain_item(text: str) -> str:
    """Задание как в книге: пропуск — «____ (to take)», без кода и ответа."""
    plain = SLOT.sub(gap, text)
    if re.search(r"[{}]", plain):
        fail(f"непонятный пропуск в задании: {text!r}")
    return escape(plain)


def jsonld(data: dict) -> str:
    # «</» внутри JSON закрыл бы <script> раньше времени.
    body = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def breadcrumbs(trail: list[tuple[str, str]]) -> tuple[str, dict]:
    """Крошки: видимые и для поисковика. Последний пункт — текущая страница."""
    links = "".join(f'<li><a href="{href(path)}">{escape(name)}</a></li>' for name, path in trail[:-1])
    html = f'<nav class="crumbs" aria-label="Хлебные крошки"><ol>{links}<li>{escape(trail[-1][0])}</li></ol></nav>'
    schema = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": SITE_URL + path}
        for i, (name, path) in enumerate(trail, 1)]}
    return html, schema


def cta(text: str = "Открыть в Telegram") -> str:
    return f'<a class="cta" href="{escape(BOT_URL)}">{escape(text)}</a>'


def layout(path: str, title: str, description: str, main: str, schema: list[dict], robots: str = "") -> str:
    url, t, d = escape(SITE_URL + path), escape(title), escape(description)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
{robots}<link rel="canonical" href="{url}">
<link rel="icon" href="{ICON}">
<meta property="og:type" content="website">
<meta property="og:locale" content="ru_RU">
<meta property="og:site_name" content="{escape(NAME)}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
{jsonld({"@context": "https://schema.org", "@graph": schema})}
<style>{CSS}</style>
</head>
<body>
<header>
<a class="brand" href="{href('/')}">{escape(NAME)}</a>
<nav aria-label="Разделы"><a href="{href('/grammar/')}">Грамматика</a><a href="{escape(BOT_URL)}">Открыть в Telegram</a></nav>
</header>
<main>
{main}
</main>
<footer>
<p>Материалы и упражнения: {escape(AUTHOR)}.</p>
<p>{escape(NAME)} — Telegram-бот <a href="{escape(BOT_URL)}">@{escape(BOT)}</a>. {FREE}.</p>
</footer>
</body>
</html>
"""


def topic_list(topics: list) -> str:
    rows = "".join(
        f'<li><a href="{href(topic_path(t))}"><b>{escape(t["title"])}</b>'
        f'<span>{counts(t["exercises"])}</span></a></li>' for t in topics)
    return f'<ol class="topics">{rows}</ol>'


def checks() -> str:
    rows = "".join(
        f"<li><p>{escape(sentence)}</p><p>Ответ: <s>{escape(wrong)}</s></p><p><b>{escape(why)}</b></p></li>"
        for sentence, wrong, why in CHECKS)
    return f'<ul class="checks">{rows}</ul>'


def index_page(content: dict) -> str:
    topics = content["topics"]
    total = counts([ex for t in topics for ex in t["exercises"]])
    themes = plural(len(topics), "тема", "темы", "тем")
    description = (f"{NAME} — Telegram-бот для английского: тетрадь по грамматике ({themes}, {total}) "
                   f"с разбором каждой ошибки и слова с интервальным повторением. {FREE}.")
    main = f"""<h1>{escape(NAME)} — тетрадь по английской грамматике и слова на повторение в Telegram</h1>
<p class="lead">Бот проверяет каждый ответ и объясняет, в чём именно ошибка, а слова возвращает на повторение, когда они почти забылись.</p>
<p>{cta()} <span class="free">{FREE}</span></p>

<h2>Не «неверно», а что именно не так</h2>
<p>Бот не просто сверяет ответ с ключом: он смотрит, какое время выбрано, на месте ли вспомогательный глагол и та ли форма, — и называет ошибку.</p>
{checks()}
<p>Рядом с разбором открывается правило и формула времени.</p>

<h2 id="grammar">Тетрадь: {themes}, {total}</h2>
<p>Времена, Passive, Conditionals, Relative clauses, Gerund, модальные глаголы, времена инфинитива, Participle, союзы. У каждой темы — правила с формулами и упражнения.</p>
{topic_list(topics)}
<ul>
<li>Тренировка форм: один глагол и одно лицо — утверждение, отрицание и вопрос в каждом пройденном времени.</li>
<li>Сделанные упражнения бот присылает в чат PDF-файлом: с ответами и первой ошибкой в каждом задании.</li>
</ul>

<h2>Слова</h2>
<ul>
<li>Пришлите боту слово в любой форме — <i lang="en">went, children, reading</i>. В ответ: начальная форма, что это за форма, перевод и примеры.</li>
<li>Интервальное повторение по алгоритму FSRS: слово возвращается ровно тогда, когда почти забылось.</li>
<li>Словарь общий на всех, расписание повторений у каждого своё.</li>
<li>«Не путай»: с чем слово путают (<i lang="en">wear — carry — put on</i>) и когда нужно именно оно.</li>
<li>Семь видов тестов, среди них тренажёр неправильных глаголов, написание слова и пропуск в примере.</li>
<li>Серия дней подряд и рейтинг недели.</li>
</ul>

<h2>Учителю</h2>
<ul>
<li>Создайте класс и добавьте бота в Telegram-группу класса: команда <code>/bind</code> привязывает группу, ученики входят одной кнопкой.</li>
<li>Задайте домашку номерами упражнений: <code>/dz 26-28</code>.</li>
<li><code>/report</code> — кто сколько сделал, сколько с первого раза, главная ошибка каждого и задания, на которых ошиблись двое и больше.</li>
<li>Контрольная на уроке: пришлите боту .docx, выберите 15, 20 или 30 минут — у учеников идёт таймер, итоги бот пишет в группу.</li>
<li>Ошибки каждого ученика: что он ввёл и почему это неверно. Верный ответ, которого не было в ключе, можно засчитать — он примется у всех.</li>
</ul>
<p class="muted">Учителем становится любой, кто создал класс: приглашение не нужно.</p>

<h2>Как начать</h2>
<ol>
<li>Откройте <a href="{escape(BOT_URL)}">@{escape(BOT)}</a> в Telegram и нажмите «Запустить».</li>
<li>Команда <code>/grammar</code> открывает тетрадь: выберите тему и упражнение. Чтобы учить слово, просто пришлите его боту.</li>
<li>Заходите каждый день: бот напомнит, когда пора повторять.</li>
</ol>
<p>{cta()}</p>

<h2>Автор материалов</h2>
<p>Материалы и упражнения: {escape(AUTHOR)}.</p>"""
    site = {"@type": "WebSite", "name": NAME, "url": SITE_URL + "/", "inLanguage": "ru", "description": description}
    return layout("/", f"{NAME} — английская грамматика и слова в Telegram, бесплатно", description, main, [site])


def grammar_index(content: dict) -> str:
    topics = content["topics"]
    themes = plural(len(topics), "тема", "темы", "тем")
    total = counts([ex for t in topics for ex in t["exercises"]])
    description = (f"Английская грамматика по темам: {themes}, {total}. "
                   "Правила с формулами и примеры заданий, проверка с разбором ошибок — в Telegram-боте.")
    crumbs, crumbs_schema = breadcrumbs([(NAME, "/"), ("Грамматика", "/grammar/")])
    main = f"""{crumbs}
<h1>Английская грамматика: {themes}</h1>
<p class="lead">{total}. На странице темы — правила с формулами и примеры заданий, а проверка с разбором ошибки — в боте.</p>
{topic_list(topics)}
<p>{cta()} <span class="free">{FREE}</span></p>"""
    return layout("/grammar/", f"Английская грамматика: {themes} с упражнениями | {NAME}", description, main, [crumbs_schema])


def rule_html(rule: dict) -> str:
    formula = f"<pre>{escape(rule['formula'])}</pre>" if rule["formula"] else ""
    return f"<h3>{escape(rule['title'])}</h3>{formula}<p class=\"lines\">{escape(rule['text'])}</p>"


def exercise_html(ex: dict) -> str:
    items = "".join(f'<li class="lines">{plain_item(item)}</li>' for item in ex["items"][:SAMPLE_ITEMS])
    return f"<h3>Упражнение {ex['id']}</h3><p>{escape(ex['task'])}</p><ol>{items}</ol>"


def pager(topics: list, i: int) -> str:
    prev = f'<a href="{href(topic_path(topics[i - 1]))}" rel="prev">← {escape(topics[i - 1]["title"])}</a>' if i else "<span></span>"
    after = topics[i + 1] if i + 1 < len(topics) else None
    nxt = f'<a href="{href(topic_path(after))}" rel="next">{escape(after["title"])} →</a>' if after else ""
    return f'<nav class="pager" aria-label="Соседние темы">{prev}{nxt}</nav>'


def topic_page(content: dict, i: int) -> str:
    topic = content["topics"][i]
    path, title = topic_path(topic), topic["title"]
    rules = [content["rules"][key] for key in rule_keys(topic)]
    total = counts(topic["exercises"])
    description = (f"{title}: правила с формулами ({', '.join(r['title'] for r in rules)}) и примеры заданий. "
                   f"В тетради {total} с проверкой и разбором ошибок в Telegram. Бесплатно.")
    crumbs, crumbs_schema = breadcrumbs([(NAME, "/"), ("Грамматика", "/grammar/"), (title, path)])
    main = f"""{crumbs}
<article>
<h1>{escape(title)}</h1>
<p class="lead">Правила с формулами и примеры заданий. В тетради по этой теме {total}.</p>
<h2>Правила</h2>
{''.join(rule_html(r) for r in rules)}
<h2>Примеры заданий</h2>
{''.join(exercise_html(ex) for ex in topic['exercises'][:SAMPLE_EXERCISES])}
<h2>Проверка с разбором ошибки — в боте</h2>
<p>Ответов здесь нет: бот проверит каждое задание и объяснит, что именно не так — не то время, пропущен вспомогательный глагол, не та форма.</p>
<p>{cta()} <span class="free">{FREE}</span></p>
</article>
{pager(content['topics'], i)}
<p><a href="{href('/grammar/')}">Все темы</a> · <a href="{href('/')}">О боте</a></p>"""
    resource = {
        "@type": "LearningResource", "name": title, "description": description, "url": SITE_URL + path,
        "inLanguage": "ru", "isAccessibleForFree": True, "educationalLevel": LEVEL,
        "learningResourceType": "упражнения", "teaches": [r["title"] for r in rules],
        "author": {"@type": "Person", "name": AUTHOR},
    }
    return layout(path, f"{title} — правила и упражнения | {NAME}", description, main, [resource, crumbs_schema])


def not_found() -> str:
    main = f"""<h1>Страница не найдена</h1>
<p>Такой страницы нет. Попробуйте <a href="{href('/grammar/')}">темы грамматики</a> или <a href="{href('/')}">главную</a>.</p>"""
    return layout("/404.html", f"Страница не найдена | {NAME}", "Такой страницы нет.", main, [],
                  '<meta name="robots" content="noindex">\n')


def sitemap(paths: list[str]) -> str:
    urls = "".join(f"<url><loc>{escape(SITE_URL + path)}</loc></url>\n" for path in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def main():
    content = load_content()
    topics = content["topics"]
    pages = {"/": index_page(content), "/grammar/": grammar_index(content)}
    pages |= {topic_path(t): topic_page(content, i) for i, t in enumerate(topics)}
    files = {path + "index.html": html for path, html in pages.items()}
    files["/404.html"] = not_found()
    files["/sitemap.xml"] = sitemap(list(pages))
    files["/robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
    # Собираем с нуля: страница удалённой темы не должна остаться в выдаче.
    if DIST.exists():
        shutil.rmtree(DIST)
    for path, text in files.items():
        target = DIST / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(f"собрано: {DIST} — {len(files)} файлов, {plural(len(topics), 'тема', 'темы', 'тем')}")


if __name__ == "__main__":
    main()
