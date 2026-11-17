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
AUTHOR = os.environ.get("AUTHOR", "учитель Байрам")
# Словарь растёт сам: в базе ~10 500 слов на 17.11.2026, округляем вниз.
WORDS = os.environ.get("WORDS", "10 000+")

SITE = Path(__file__).parent
CONTENT = SITE.parent / "backend/src/vocab/grammar/content.json"
DIST = SITE / "dist"
TG_ICON = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.9 4.3 18.7 19.4c-.2 1-.9 1.3-1.8.8'
           'l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.3-5 9.2-8.3c.4-.4-.1-.6-.6-.2L6.1 13 1.2 11.5c-1-.3-1-1 .2-1.5L20.6 2.7'
           'c.9-.3 1.6.2 1.3 1.6z"/></svg>')


def fill(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    if "{{" in template:
        raise SystemExit("site/build.py: в шаблоне осталась неподставленная метка {{…}}")
    return template


def main():
    topics = json.loads(CONTENT.read_text(encoding="utf-8"))["topics"]
    html = fill((SITE / "index.html").read_text(encoding="utf-8"), {
        "SITE_URL": escape(SITE_URL), "BOT": escape(BOT), "BOT_URL": escape(f"https://t.me/{BOT}"),
        "NAME": escape(NAME), "AUTHOR": escape(AUTHOR), "WORDS": escape(WORDS), "TG_ICON": TG_ICON,
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
