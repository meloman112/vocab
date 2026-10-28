"""DTO. Доменная строка из базы наружу as is не уходит: новая техническая
колонка не должна автоматически утечь в ответ."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class AddWord(BaseModel):
    # Не только слово: из фразы или предложения достаются устойчивые выражения.
    word: str = Field(min_length=1, max_length=300)


class Review(BaseModel):
    card_id: int
    rating: int = Field(ge=1, le=4)


class Example(BaseModel):
    en: str
    ru: str


class CardOut(BaseModel):
    id: int
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
    due: datetime


class WordEntry(BaseModel):
    """Ответ на присланное слово: содержимое из общего словаря плюс то,
    что касается именно этого запроса."""

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
