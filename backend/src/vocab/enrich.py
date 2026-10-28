"""Запросы к DeepSeek: содержимое карточки для леммы и поиск фраз в тексте."""

import json
import logging
from typing import Any

import httpx

from .config import Settings

log = logging.getLogger(__name__)

WORD_PROMPT = """\
Ты составляешь карточки для запоминания английских слов и устойчивых фраз.
Отвечай только JSON-объектом с полями:

translation — перевод на русский, 1-3 самых частых значения через запятую.
ipa — транскрипция IPA без косых черт.
pos — часть речи одним английским словом (noun, verb, adjective, adverb, phrase).
forms — для глагола три формы через « · » (go · went · gone), для
  существительного с неправильным множественным числом — ед. и мн. (child · children),
  иначе пустая строка.
irregular — true, если глагол неправильный или множественное число неправильное.
examples — массив из двух объектов {"en": ..., "ru": ...}: простые предложения
  уровня A2-B1 не длиннее 12 слов и их перевод.
zipf — насколько часто это встречается в английском, по шкале Zipf с одним
  знаком после запятой: 7 — как "the", 6 — как "go", 5 — как "read",
  4 — как "reliable", 3 — как "redundant", 2 — совсем редко.
level — уровень CEFR, на котором это обычно изучают: A1, A2, B1, B2, C1 или C2.

Никаких пояснений и markdown вне JSON.
"""

PHRASES_PROMPT = """\
Тебе пришлют английский текст. Найди в нём устойчивые выражения, которые стоит
учить целиком: фразовые глаголы (give up), идиомы (by the way), парные и
повторные конструкции (more and more, the more... the better), устойчивые
связки (as soon as, in order to).

Отдельные слова и свободные сочетания не нужны. Каждую фразу приведи к
словарной форме в нижнем регистре: gave up → give up.

Отвечай только JSON-объектом {"phrases": [...]}. Ничего не нашёл — пустой массив.
"""

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

TIMEOUT = httpx.Timeout(20.0)
ATTEMPTS = 2


class EnrichError(Exception):
    """ИИ не ответил или ответил не по формату — и так оба раза."""


def parse_word(content: str) -> dict[str, Any]:
    """Разбирает ответ модели. Отдельно от запроса, потому что ломается
    именно здесь: сеть либо работает, либо нет, а формат ответа плавает."""
    data = json.loads(content)
    # Валидный JSON без перевода — самый вероятный кривой ответ. Без проверки
    # слово уехало бы в общий словарь пустым, сразу всем.
    missing = [name for name in ("translation", "ipa", "pos") if not data.get(name)]
    if missing:
        raise ValueError(f"в ответе модели нет полей: {', '.join(missing)}")

    examples = [
        {"en": str(e["en"]).strip(), "ru": str(e["ru"]).strip()}
        for e in data.get("examples") or []
        if isinstance(e, dict) and e.get("en") and e.get("ru")
    ]
    if not examples:
        raise ValueError("в ответе модели нет примеров")

    return {
        "translation": str(data["translation"]).strip(),
        "ipa": str(data["ipa"]).strip(),
        "pos": str(data["pos"]).strip(),
        "forms": str(data.get("forms") or "").strip(),
        "irregular": data.get("irregular") is True,
        "examples": examples,
        "zipf": _zipf(data.get("zipf")),
        # Уровень только упорядочивает выдачу: незнакомое значение — не повод
        # терять перевод, слово просто уйдёт в конец.
        "level": data.get("level") if data.get("level") in LEVELS else None,
    }


def _zipf(value: Any) -> float:
    # Оценка нужна только фразам и только для порядка выдачи: кривое
    # число не повод терять перевод, но и выйти за шкалу оно не должно.
    try:
        return min(max(float(value), 0.0), 8.0)
    except (TypeError, ValueError):
        return 0.0


def parse_phrases(content: str) -> list[str]:
    phrases = json.loads(content)["phrases"]
    return [" ".join(str(p).split()).lower() for p in phrases if str(p).strip()]


async def _chat(cfg: Settings, system: str, user: str) -> str:
    payload = {
        "model": cfg.deepseek_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # Строгий JSON на стороне API: без него модель периодически
        # оборачивает ответ в ```json и парсер падает.
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(base_url=cfg.deepseek_base_url, timeout=TIMEOUT) as client:
        response = await client.post(
            "/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {cfg.deepseek_api_key}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def _ask(cfg: Settings, system: str, user: str, parse):
    """Запрос с одним повтором. Очередь с бэкоффом не нужна: пользователь
    ждёт ответа в чате и при отказе просто пришлёт слово ещё раз."""
    if not cfg.deepseek_api_key:
        raise EnrichError("DEEPSEEK_API_KEY пуст")

    for attempt in range(1, ATTEMPTS + 1):
        try:
            return parse(await _chat(cfg, system, user))
        except Exception as exc:  # noqa: BLE001 — причина уходит в лог, итог — в EnrichError
            log.warning("ИИ: попытка %s для %r не удалась: %s", attempt, user, exc)
    raise EnrichError(f"ИИ не ответил на {user!r}")


async def fetch_word(cfg: Settings, lemma: str) -> dict[str, Any]:
    return await _ask(cfg, WORD_PROMPT, lemma, parse_word)


async def find_phrases(cfg: Settings, text: str) -> list[str]:
    return await _ask(cfg, PHRASES_PROMPT, text, parse_phrases)
