"""Обогащение карточки через DeepSeek: перевод, транскрипция, пример."""

import json
import logging

import asyncpg
import httpx

from . import repo
from .config import Settings

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ("translation", "ipa", "pos", "example", "example_ru")

SYSTEM_PROMPT = """\
Ты помогаешь составлять карточки для запоминания английских слов.
Отвечай только JSON-объектом с полями translation, ipa, pos, example, example_ru.

translation — перевод на русский, 1-3 варианта через запятую.
ipa — транскрипция IPA без косых черт.
pos — часть речи одним английским словом (noun, verb, adjective, adverb, phrase).
example — простое предложение с этим словом, уровень A2-B1, не длиннее 12 слов.
example_ru — перевод предложения на русский.

Если слово многозначное, выбирай значение, подходящее к присланному контексту.
Никаких пояснений и markdown вне JSON.
"""

TIMEOUT = httpx.Timeout(20.0)


def _user_prompt(word: str, context: str | None) -> str:
    if not context:
        return f"Слово: {word}"
    return f"Слово: {word}\nКонтекст (страница, где оно встретилось): {context}"


def parse_answer(content: str) -> dict[str, str]:
    """Разбирает ответ модели. Отдельно от запроса, потому что ломается
    именно здесь: сеть либо работает, либо нет, а формат ответа плавает."""
    data = json.loads(content)
    # Модель может вернуть валидный JSON без нужного поля — тогда карточка
    # уехала бы в 'ready' с пустым переводом, и починить её было бы нечем.
    missing = [name for name in REQUIRED_FIELDS if not data.get(name)]
    if missing:
        raise ValueError(f"в ответе модели нет полей: {', '.join(missing)}")
    return {name: str(data[name]).strip() for name in REQUIRED_FIELDS}


async def fetch_fields(cfg: Settings, word: str, context: str | None) -> dict[str, str]:
    """Один запрос к модели. Бросает исключение, если ответ не разобрать."""
    payload = {
        "model": cfg.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(word, context)},
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
        content = response.json()["choices"][0]["message"]["content"]

    return parse_answer(content)


async def enrich_card(pool: asyncpg.Pool, cfg: Settings, card_id: int, word: str,
                      source_url: str | None) -> None:
    """Фоновая задача: обогатить карточку или пометить её failed.

    Ретраев ровно два (первый запрос плюс один повтор) и они не размазаны
    по времени: очередь с бэкоффом ради личного словаря — отдельный сервис,
    а неудачную карточку и так можно перезапустить кнопкой.
    """
    if not cfg.deepseek_api_key:
        log.warning("DEEPSEEK_API_KEY пуст, карточка %s остаётся pending", card_id)
        return

    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            fields = await fetch_fields(cfg, word, source_url)
        except Exception as exc:  # noqa: BLE001 — причина уходит в лог ниже
            last_error = exc
            log.warning("обогащение %s: попытка %s не удалась: %s", card_id, attempt, exc)
            continue

        async with pool.acquire() as conn:
            await repo.set_enrichment(conn, card_id, fields)
        return

    log.error("обогащение %s провалено: %s", card_id, last_error)
    async with pool.acquire() as conn:
        await repo.mark_failed(conn, card_id)
