"""DTO. Доменная строка из базы наружу as is не уходит: новая техническая
колонка не должна автоматически утечь в ответ."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AddWord(BaseModel):
    # Не только слово: из фразы или предложения достаются устойчивые выражения.
    word: str = Field(min_length=1, max_length=300)
    # Какое из значений леммы нужно: кнопка «ещё: to book — глагол».
    pos: Literal["noun", "verb", "adjective", "adverb"] | None = None
    # «Добавить как есть» под подсказкой опечатки: helf — не help, а helf.
    as_is: bool = False


class Review(BaseModel):
    card_id: int
    rating: int = Field(ge=1, le=4)


class Example(BaseModel):
    en: str
    ru: str


class CardOut(BaseModel):
    id: int
    # Жалоба идёт на слово общего словаря, а не на личную карточку.
    word_id: int
    word: str
    translation: str
    ipa: str
    pos: str
    forms: str
    irregular: bool
    examples: list[Example]
    # Рейтинг слова: место по частоте в языке («топ-500») и сколько людей учат.
    top: str
    learners: int
    # У леммы есть другие части речи: на лицевой стороне нужна подсказка,
    # иначе по «book» не понять, спрашивают «книгу» или «бронировать».
    homonym: bool
    due: datetime


class OtherSense(BaseModel):
    """Другая часть речи той же леммы. translation — None, если в словаре
    её ещё нет: перевод появится, когда её выберут."""

    pos: str
    translation: str | None


class WordEntry(BaseModel):
    """Ответ на присланное слово: содержимое из общего словаря плюс то,
    что касается именно этого запроса."""

    # id слова в общем словаре — для кнопки «сообщить об ошибке».
    id: int
    lemma: str
    # «reading — форма на -ing: Continuous или герундий» — если прислали не лемму.
    form_note: str | None
    translation: str
    ipa: str
    pos: str
    forms: str
    irregular: bool
    examples: list[Example]
    top: str
    # Сколько человек учат слово, включая только что добавившего.
    learners: int
    # Различие «добавили» и «уже было» нужно боту, чтобы ответить честно.
    created: bool
    others: list[OtherSense]


class AddWordOut(BaseModel):
    entries: list[WordEntry]


class QueueOut(BaseModel):
    cards: list[CardOut]


class ReviewOut(BaseModel):
    card_id: int
    due: datetime
    state: int


class ForecastDay(BaseModel):
    day: date
    count: int


class StatsOut(BaseModel):
    total: int
    learned: int
    due_now: int
    due_today: int
    forecast: list[ForecastDay]
    # Дней подряд с повторением; пропущенный день — уже 0.
    streak: int
    best_streak: int


class LeaderRow(BaseModel):
    place: int
    name: str
    xp: int
    streak: int


class LeaderboardOut(BaseModel):
    top: list[LeaderRow]
    # Своё место, даже если оно ниже топа. None — на этой неделе не занимался.
    me: LeaderRow | None


class ReminderTarget(BaseModel):
    tg_id: int
    streak: int
    # Дней с последнего повторения; None — не повторял ни разу.
    gap: int | None
    due: int


class Ban(BaseModel):
    word: str = Field(min_length=1, max_length=100)


class TopWord(BaseModel):
    word: str
    translation: str
    top: str
    learners: int
    # Есть ли слово у того, кто спрашивает.
    mine: bool


class SearchHit(BaseModel):
    id: int
    word: str
    translation: str
    due: datetime


class WeakCard(BaseModel):
    id: int
    word: str
    translation: str
    examples: list[Example]
    lapses: int


class Cloze(BaseModel):
    # «She _____ home yesterday.» — пропуск на месте формы слова.
    text: str
    # Форма, стоящая в предложении (went), а не лемма.
    answer: str
    ru: str


class QuizCard(CardOut):
    # EN→RU: переводы; RU→EN: слова. Правильный среди них, порядок случайный.
    choices_ru: list[str]
    choices_en: list[str]
    # None — ни в одном примере формы слова не нашлось.
    cloze: Cloze | None


class QuizOut(BaseModel):
    cards: list[QuizCard]


ReportReason = Literal["typo", "translation", "example", "other"]


class Report(BaseModel):
    word_id: int
    reason: ReportReason
    comment: str | None = Field(default=None, max_length=500)


class Me(BaseModel):
    is_admin: bool


class AdminWord(BaseModel):
    id: int
    lemma: str
    translation: str
    ipa: str
    pos: str
    forms: str
    irregular: bool
    examples: list[Example]
    level: str | None
    banned: bool


class ReportedWord(AdminWord):
    reports: int
    reasons: list[ReportReason]
    comments: list[str]
    last_at: datetime


class WordEdit(BaseModel):
    """Всё, что админ может поменять. Лемму и часть речи — нет: это ключ
    слова, и карточки людей на него уже ссылаются."""

    translation: str = Field(min_length=1, max_length=200)
    ipa: str = Field(max_length=100)
    forms: str = Field(max_length=200)
    irregular: bool
    examples: list[Example] = Field(min_length=1, max_length=5)
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None
    banned: bool


class AdminSummary(BaseModel):
    users: int
    active_week: int
    words: int
    banned: int
    open_reports: int
