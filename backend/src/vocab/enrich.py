"""Запросы к DeepSeek: содержимое карточки для леммы и поиск фраз в тексте."""

import json
import logging
import re
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

Если указана часть речи, вся карточка — перевод, примеры, формы — должна быть
в этой части речи, и pos в ответе — ровно она: «book, часть речи: verb» —
бронировать, а не книга.

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

TRANSLATE_PROMPT = """\
Ты переводчик для русскоязычного ученика, который учит английский.
Тебе пришлют английский текст — фразу или предложение из учебника, иногда
с пропусками (___) или подсказками в скобках. Переведи его на русский
естественно и точно; пропуски и скобки оставь как есть.

Отвечай только JSON-объектом {"translation": "..."}.
"""

TEST_PROMPT = """\
Ты помогаешь учителю английского перенести его контрольную в онлайн-тест.
Тебе пришлют текст контрольной. Найди задания, где ученик вписывает ответ:
раскрыть скобки, вставить пропуск, поставить глагол в нужную форму. Задания
с выбором варианта (a, b, c) тоже превращай в пропуск с верным ответом,
а варианты пиши в подсказке через « / »: [were] (am / was / were).

Каждое задание — одна строка: предложение целиком, на месте пропуска —
верный ответ в квадратных скобках. Если верных ответов несколько, перечисли
их через «|»: [has lived|has been living]. Подсказку из задания (глагол
в скобках) поставь сразу после пропуска в круглых скобках:
«She (not like) coffee.» → «She [doesn't like] (not like) coffee.»
Сокращения не дублируй: don't и do not и так считаются одним ответом.
Заголовки, инструкции и нумерацию не переноси.

Если ответ есть в тексте (ключ, ответы в конце) — бери его, guessed: false.
Если ответа нет или ответ в ключе, по-твоему, неверен — поставь свой,
guessed: true, а в note коротко по-русски объясни, что проверить.

Отвечай только JSON-объектом
{"questions": [{"line": "...", "guessed": false, "note": ""}]}.
"""

RECHECK_PROMPT = """\
Ты проверяешь упражнение по грамматике английского. Тебе пришлют задание,
предложение с пропуском (подсказка в скобках), ответ из ключа и ответ
ученика. Ключ иногда знает не все верные ответы. Реши, верен ли ответ
ученика в этом предложении: грамматически правильный, подходит по смыслу
и выполняет задание (то время, тот глагол). Опечатка — это неверно.

Отвечай только JSON-объектом {"ok": true|false, "why": "..."}, в why —
одно-два коротких предложения по-русски для ученика.
"""
CONTRAST_PROMPT = """\
Ты помогаешь русскоязычному ученику уровня A2-B1 не путать английские слова.
Тебе пришлют английское слово, часть речи и перевод. Отвечай только JSON-объектом:

others — до 3 разных английских слов, которые с этим словом реально путают
  русскоязычные: у них тот же перевод на русский, но другое употребление
  (wear — carry — put on), или похожее написание и звучание (lie — lay).
  Каждое — {"word": ..., "note": ...}, note — по-русски до 6 слов, когда
  нужно именно оно («нести в руках, с собой»). Не с чем путать — [].
note — по-русски до 10 слов: когда нужно именно это слово.
collocations — 2-3 самых частых сочетания с этим словом по-английски.
quiz — если others не пуст: {"text": английское предложение до 12 слов, где на
  месте этого слова стоит ___, а слова из others там были бы явной ошибкой;
  "ru": перевод предложения; "options": это слово и слова из others в той
  форме, что нужна в предложении, правильное первым}. Если others пуст — null.

Никаких пояснений и markdown вне JSON.
"""

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# Локальная Qwen на общем сервере: карточка генерируется ~50 с, а занятый
# чужим запросом слот добавляет очередь.
TIMEOUT = httpx.Timeout(120.0)
ATTEMPTS = 2


BLANK = "___"


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


def parse_contrast(content: str) -> dict[str, Any]:
    """С чем путают слово. Кривой тест выбрасывается, а не чинится сверх
    простого: без пропуска или с одним вариантом это не упражнение."""
    data = json.loads(content)
    others, seen = [], set()
    for other in data.get("others") or []:
        word = str(other.get("word") or "").strip() if isinstance(other, dict) else ""
        if word and word.lower() not in seen:
            seen.add(word.lower())
            others.append({"word": word, "note": str(other.get("note") or "").strip()})
    collocations = [str(c).strip() for c in data.get("collocations") or [] if str(c).strip()]
    return {
        "others": others,
        "note": str(data.get("note") or "").strip(),
        "collocations": collocations[:3],
        "quiz": _contrast_quiz(data.get("quiz")) if others else None,
    }


def _contrast_quiz(quiz: Any) -> dict[str, Any] | None:
    if not isinstance(quiz, dict):
        return None
    options = list(dict.fromkeys(str(o).strip() for o in quiz.get("options") or [] if str(o).strip()))
    text = str(quiz.get("text") or "").strip()
    if len(options) < 2 or not quiz.get("ru"):
        return None
    if BLANK not in text:
        # Модель иногда пишет слово вместо пропуска: «She likes to wear a hat».
        text = re.sub(rf"\b{re.escape(options[0])}\b", BLANK, text, count=1)
    if BLANK not in text:
        return None
    return {"text": text, "ru": str(quiz["ru"]).strip(), "options": options}


async def fetch_contrast(cfg: Settings, lemma: str, pos: str, translation: str) -> dict[str, Any]:
    return await _ask(cfg, CONTRAST_PROMPT, f"{lemma}\n{pos}\n{translation}", parse_contrast)


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


# Сколько запросов к модели в пути: фоновое заполнение ждёт, пока их нет,
# чтобы не занимать общий слот, когда человек ждёт карточку.
in_flight = 0


async def _chat(cfg: Settings, system: str, user: str, timeout: httpx.Timeout = TIMEOUT) -> str:
    global in_flight
    in_flight += 1
    try:
        return await _post(cfg, system, user, timeout)
    finally:
        in_flight -= 1


async def _post(cfg: Settings, system: str, user: str, timeout: httpx.Timeout) -> str:
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
        # Qwen3 по умолчанию сначала рассуждает: при ~4 токенах в секунду
        # это минуты ожидания ради карточки, которую она пишет и без них.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    async with httpx.AsyncClient(base_url=cfg.deepseek_base_url, timeout=timeout) as client:
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


async def fetch_word(cfg: Settings, lemma: str, pos: str | None = None) -> dict[str, Any]:
    """Карточка для леммы. С pos — именно в этой части речи: to book
    «бронировать», а не основное «книга»."""
    if pos is None:
        return await _ask(cfg, WORD_PROMPT, lemma, parse_word)
    return await _ask(cfg, WORD_PROMPT, f"{lemma}\nЧасть речи: {pos}", _parse_as(pos))


def _parse_as(pos: str):
    def parse(content: str) -> dict[str, Any]:
        fields = parse_word(content)
        # Модель иногда отвечает про основное значение вопреки просьбе. Такую
        # карточку под этой частью речи сохранять нельзя: под verb лежала бы
        # «книга», поэтому ответ считается кривым и уходит на повтор.
        if fields["pos"] != pos:
            raise ValueError(f"просили {pos}, модель ответила {fields['pos']}")
        return fields
    return parse


async def find_phrases(cfg: Settings, text: str) -> list[str]:
    return await _ask(cfg, PHRASES_PROMPT, text, parse_phrases)


def parse_translation(content: str) -> str:
    text = " ".join(str(json.loads(content).get("translation") or "").split())
    if not text:
        raise ValueError("в ответе модели нет перевода")
    return text


async def translate(cfg: Settings, text: str) -> str:
    """Перевод фразы или предложения целиком — для выделенного в мини-аппе."""
    return await _ask(cfg, TRANSLATE_PROMPT, text, parse_translation)


def parse_test(content: str) -> list[dict[str, Any]]:
    rows = json.loads(content)["questions"]
    return [
        {"line": " ".join(str(r["line"]).split()), "guessed": bool(r.get("guessed")),
         "note": str(r.get("note") or "").strip()}
        for r in rows if str(r.get("line") or "").strip()
    ]


async def convert_test(cfg: Settings, text: str) -> list[dict[str, Any]]:
    """Контрольная учителя → строки теста. Одна попытка с долгим ожиданием:
    ответ длинный, а учитель ждёт и при отказе нажмёт ещё раз."""
    if not cfg.deepseek_api_key:
        raise EnrichError("DEEPSEEK_API_KEY пуст")
    try:
        return parse_test(await _chat(cfg, TEST_PROMPT, text, httpx.Timeout(300.0)))
    except Exception as exc:  # noqa: BLE001 — причина уходит в лог, итог — в EnrichError
        log.warning("ИИ: контрольная не разобрана: %s", exc)
        raise EnrichError("ИИ не разобрал контрольную") from exc


def parse_recheck(content: str) -> dict[str, Any]:
    data = json.loads(content)
    if not isinstance(data.get("ok"), bool):
        raise ValueError("в ответе модели нет ok")
    return {"ok": data["ok"], "why": " ".join(str(data.get("why") or "").split())}


async def recheck(cfg: Settings, task: str, sentence: str, key: list[str], answer: str) -> dict[str, Any]:
    """Второе мнение по ответу, который движок тетради не принял. Одна
    попытка: прокси рвёт запрос на 60 с, а ученик и так может нажать ещё раз."""
    if not cfg.deepseek_api_key:
        raise EnrichError("DEEPSEEK_API_KEY пуст")
    text = f"Задание: {task}\nПредложение: {sentence}\nКлюч: {' / '.join(key)}\nУченик: {answer}"
    try:
        return parse_recheck(await _chat(cfg, RECHECK_PROMPT, text, httpx.Timeout(50.0)))
    except Exception as exc:  # noqa: BLE001 — причина уходит в лог, итог — в EnrichError
        log.warning("ИИ: перепроверка %r не удалась: %s", text, exc)
        raise EnrichError("ИИ не ответил") from exc
