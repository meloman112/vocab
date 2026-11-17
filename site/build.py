"""Лендинг: site/index.html с подставленными адресом, ботом и цифрами тетради → site/dist/.

Только стандартная библиотека. Адрес, бот и название можно переопределить окружением.
"""

import json
import os
import shutil
from html import escape
from pathlib import Path

SITE_URL = os.environ.get("SITE_URL", "https://vocab.blick.uz").rstrip("/")
BOT = os.environ.get("BOT", "workbookonlinebot")
NAME = os.environ.get("NAME", "Vocab")
# Словарь растёт сам: в базе ~10 500 слов на 17.11.2026, округляем вниз.
WORDS = os.environ.get("WORDS", "10 000+")

SITE = Path(__file__).parent
CONTENT = SITE.parent / "backend/src/vocab/grammar/content.json"
DIST = SITE / "dist"
TG_ICON = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.9 4.3 18.7 19.4c-.2 1-.9 1.3-1.8.8'
           'l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.3-5 9.2-8.3c.4-.4-.1-.6-.6-.2L6.1 13 1.2 11.5c-1-.3-1-1 .2-1.5L20.6 2.7'
           'c.9-.3 1.6.2 1.3 1.6z"/></svg>')


def faq(topics: list[dict]) -> list[tuple[str, str]]:
    names = ", ".join(t["title"] for t in topics)
    return [
        ("Это правда бесплатно?",
         "Да. Без подписок, рекламы и платных функций — для учеников и для учителей."),
        ("Нужно что-то устанавливать?",
         f"Нет. Всё работает в Telegram: бот @{BOT} и мини-приложение внутри него, на телефоне и на компьютере."),
        ("Какие темы грамматики есть?",
         f"{len(topics)} тем: {names}. У каждой — правило с формулой и упражнения."),
        ("Для какого уровня?",
         "Грамматика — от A2 до B2. Слова — любые: пришлите своё или возьмите набор 3000 слов уровня B1."),
        ("Как бот учит слова?",
         "Пришлите слово в любой форме — бот найдёт начальную, даст перевод и примеры и добавит в повторение. "
         "Алгоритм FSRS возвращает слово, когда оно почти забылось; тренировки — перевод, пары, на слух, "
         "написание, пропуск в примере, неправильные глаголы."),
        ("Как учителю создать класс?",
         "В боте нажмите «Я преподаю» и создайте класс — приглашение не нужно. Ученики входят по ссылке, "
         "а учитель даёт тесты на дом или на урок с таймером и видит ошибки каждого."),
        ("Кто автор упражнений?",
         "Материалы — Байрам, преподаватель английского. Разработка — Бабур."),
    ]


def faq_html(items: list[tuple[str, str]]) -> str:
    return "\n".join(
        f'        <details class="reveal"><summary>{escape(q)}</summary><p>{escape(a)}</p></details>'
        for q, a in items
    )


def faq_ld(items: list[tuple[str, str]]) -> str:
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def fill(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    if "{{" in template:
        raise SystemExit("site/build.py: в шаблоне осталась неподставленная метка {{…}}")
    return template


def main():
    topics = json.loads(CONTENT.read_text(encoding="utf-8"))["topics"]
    questions = faq(topics)
    html = fill((SITE / "index.html").read_text(encoding="utf-8"), {
        "SITE_URL": escape(SITE_URL), "BOT": escape(BOT), "BOT_URL": escape(f"https://t.me/{BOT}"),
        "NAME": escape(NAME), "WORDS": escape(WORDS), "TG_ICON": TG_ICON,
        "FAQ": faq_html(questions), "FAQ_LD": faq_ld(questions),
        "TOPICS": str(len(topics)), "EXERCISES": str(sum(len(t["exercises"]) for t in topics)),
    })
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir()
    (DIST / "index.html").write_text(html, encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{escape(SITE_URL)}/</loc></url></urlset>\n", encoding="utf-8")
    print(f"site/dist: лендинг для {SITE_URL}")


if __name__ == "__main__":
    main()
