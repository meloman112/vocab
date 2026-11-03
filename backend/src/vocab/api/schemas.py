"""DTO. Доменная строка из базы наружу as is не уходит: новая техническая
колонка не должна автоматически утечь в ответ."""

from datetime import date, datetime
from typing import Annotated, Literal

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


class TextLookup(BaseModel):
    """Перевод выделенного предложения целиком — от модели, без карточки."""

    kind: Literal["text"]
    text: str
    translation: str


class WordLookup(BaseModel):
    """Перевод выделенного слова. Карточка не заводится: saved — есть ли
    она уже, чтобы вместо «Добавить» показать «Уже в твоих словах»."""

    kind: Literal["word"]
    id: int
    lemma: str
    form_note: str | None
    translation: str
    ipa: str
    pos: str
    forms: str
    examples: list[Example]
    saved: bool


LookupOut = Annotated[WordLookup | TextLookup, Field(discriminator="kind")]


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


class ClientError(BaseModel):
    message: str = Field(max_length=500)
    stack: str = Field(default="", max_length=4000)
    where: str = Field(default="", max_length=200)
    ua: str = Field(default="", max_length=300)


class Me(BaseModel):
    is_admin: bool
    # Учителю в меню показывается «Ученики». Админ — всегда учитель.
    is_teacher: bool
    # Сколько заданий тетради сделано и сколько из них пока с ошибкой.
    grammar_done: int
    grammar_wrong: int


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


# --- тетрадь -------------------------------------------------------------------

# Ограничения — от мусора, а не от учеников: в задании до ~10 пропусков,
# полное предложение в Passive короче 200 символов.
class GrammarMistake(BaseModel):
    slot: int = Field(ge=0, le=30)
    answer: str = Field(min_length=1, max_length=300)
    # Разбор движка: «Не то время. «yesterday» — …». Учитель видит его как есть.
    why: str = Field(default="", max_length=300)


class GrammarAttempt(BaseModel):
    item: str = Field(pattern=r"^\d{1,3}-\d{1,3}$")
    clean: bool
    answers: list[str] = Field(max_length=30)
    mistakes: list[GrammarMistake] = Field(default=[], max_length=50)


class GrammarResult(BaseModel):
    clean: bool
    was_wrong: bool
    answers: list[str]


class GrammarProgress(BaseModel):
    results: dict[str, GrammarResult]
    # item → номер пропуска → ответы, которые засчитал учитель.
    accepted: dict[str, dict[int, list[str]]]


class LegacyResult(BaseModel):
    """Запись прежнего мини-аппа из CloudStorage: {clean, wasWrong, answers}."""

    clean: bool
    wasWrong: bool = False
    answers: list[str | None] = Field(default=[], max_length=30)


class GrammarImport(BaseModel):
    items: dict[str, LegacyResult] = Field(max_length=5000)


class ImportOut(BaseModel):
    imported: int


class PdfPart(BaseModel):
    text: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, max_length=300)
    hint: str | None = Field(default=None, max_length=300)


class PdfItem(BaseModel):
    n: int
    done: bool
    parts: list[PdfPart] = Field(max_length=40)


class PdfExercise(BaseModel):
    id: int
    task: str = Field(max_length=500)
    items: list[PdfItem] = Field(max_length=40)


class PdfRequest(BaseModel):
    exercises: list[PdfExercise] = Field(min_length=1, max_length=200)


class Student(BaseModel):
    user_id: int
    name: str
    done: int
    first_try: int
    wrong_now: int
    # Ошибки, которые учитель ещё не засчитал: всего и за неделю.
    mistakes: int
    mistakes_week: int
    last_at: datetime | None


class StudentResult(BaseModel):
    item: str
    clean: bool
    was_wrong: bool
    answers: list[str | None]
    updated_at: datetime


class StudentMistake(BaseModel):
    id: int
    item: str
    slot: int
    answer: str
    why: str
    created_at: datetime
    accepted: bool


class StudentDetail(BaseModel):
    user_id: int
    name: str
    results: list[StudentResult]
    mistakes: list[StudentMistake]


class CommonMistake(BaseModel):
    item: str
    students: int
    attempts: int
    answers: list[str]


class Teacher(BaseModel):
    user_id: int
    tg_id: int
    name: str


class Invite(BaseModel):
    code: str
    ttl_days: int


class Redeemed(BaseModel):
    # Кто выдал ссылку — бот скажет ему, что учитель появился.
    inviter_tg_id: int | None
