"""DTO. Доменная строка из базы наружу as is не уходит: новая техническая
колонка в cards не должна автоматически утечь в ответ."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class AddWord(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=2000)


class Review(BaseModel):
    card_id: int
    rating: int = Field(ge=1, le=4)


class CardOut(BaseModel):
    id: int
    word: str
    status: str
    translation: str | None
    ipa: str | None
    pos: str | None
    example: str | None
    example_ru: str | None
    due: datetime


class AddWordOut(BaseModel):
    id: int
    word: str
    status: str
    # Различие «создали» и «уже было» нужно боту, чтобы ответить
    # «уже есть» вместо второго «added».
    created: bool


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
    pending: int
    failed: int
    due_now: int
    due_today: int
    forecast: list[ForecastDay]


class DueUser(BaseModel):
    tg_id: int
    due: int


class FailedCard(BaseModel):
    id: int
    word: str


class SearchHit(BaseModel):
    id: int
    word: str
    translation: str | None
    status: str
    due: datetime


class WeakCard(BaseModel):
    id: int
    word: str
    translation: str | None
    example: str | None
    lapses: int
