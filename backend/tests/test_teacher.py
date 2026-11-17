"""Бот открыт всем: учитель видит только учеников своих классов, а учителем
становится любой, кто создал класс."""

import asyncio
import contextlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from vocab import repo
from vocab.api import auth, classwork, grammar, groups, schemas
from vocab.api.auth import Identity, Teacher

ADMIN_TG = 1
TEACHER = Teacher(user_id=7, scope=7)
ADMIN = Teacher(user_id=1, scope=None)


class Pool:
    @contextlib.asynccontextmanager
    async def acquire(self):
        yield None


REQUEST = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=Pool())), headers={})


def fake(monkeypatch, name, result):
    """Подменяет функцию repo и возвращает список её вызовов (без conn)."""
    calls = []

    async def call(conn, *args):
        calls.append(args)
        return result

    monkeypatch.setattr(repo, name, call)
    return calls


def status_of(coroutine) -> int:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(coroutine)
    return exc.value.status_code


@pytest.fixture
def guard(monkeypatch):
    """teacher() для пользователя с users.id = 7 и заданным tg_id."""
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(is_admin=lambda tg_id: tg_id == ADMIN_TG))
    fake(monkeypatch, "ensure_user", 7)
    return lambda tg_id: asyncio.run(auth.teacher(REQUEST, Identity(tg_id, None)))


def test_teacher_is_scoped_to_own_classes(monkeypatch, guard):
    fake(monkeypatch, "is_teacher", True)
    assert guard(500) == Teacher(user_id=7, scope=7)


def test_admin_sees_everyone(monkeypatch, guard):
    fake(monkeypatch, "is_teacher", False)
    assert guard(ADMIN_TG) == Teacher(user_id=7, scope=None)


def test_not_a_teacher_is_forbidden(monkeypatch, guard):
    fake(monkeypatch, "is_teacher", False)
    with pytest.raises(HTTPException) as exc:
        guard(500)
    assert exc.value.status_code == 403


def test_students_list_is_asked_for_own_scope(monkeypatch):
    calls = fake(monkeypatch, "students", [])
    asyncio.run(grammar.get_students(REQUEST, TEACHER))
    asyncio.run(grammar.get_students(REQUEST, ADMIN))
    assert calls == [(7,), (None,)]


def test_foreign_student_is_not_found(monkeypatch):
    fake(monkeypatch, "student", {"user_id": 42, "name": "Чужой"})
    calls = fake(monkeypatch, "teaches", False)
    assert status_of(grammar.get_student(42, REQUEST, TEACHER)) == 404
    assert calls == [(7, 42)]


def test_own_student_is_shown(monkeypatch):
    fake(monkeypatch, "student", {"user_id": 42, "name": "Свой"})
    fake(monkeypatch, "teaches", True)
    fake(monkeypatch, "student_results", [])
    fake(monkeypatch, "student_mistakes", [])
    assert asyncio.run(grammar.get_student(42, REQUEST, TEACHER)).name == "Свой"


def test_accepting_foreign_mistake_is_not_found(monkeypatch):
    # repo.accept_mistake не находит ошибку ученика вне классов учителя.
    calls = fake(monkeypatch, "accept_mistake", None)
    assert status_of(grammar.accept_mistake(5, REQUEST, TEACHER)) == 404
    assert calls == [(5, 7, 7)]


def test_admin_accepts_for_everyone(monkeypatch):
    calls = fake(monkeypatch, "accept_mistake", {"item": "1-0"})
    asyncio.run(grammar.accept_mistake(5, REQUEST, ADMIN))
    assert calls == [(5, 1, None)]


def test_progress_reads_accepted_answers_of_this_student(monkeypatch):
    fake(monkeypatch, "grammar_results", [])
    calls = fake(monkeypatch, "grammar_accepted", [{"item": "1-0", "slot": 0, "answer": "goes"}])
    progress = asyncio.run(grammar.get_progress(REQUEST, 42))
    assert calls == [(42,)]
    assert progress.accepted == {"1-0": {0: ["goes"]}}


def test_taught_condition_lets_admin_through_and_filters_by_class():
    sql = repo._taught("u.id", 2)
    assert sql.startswith("($2::bigint is null or u.id in (")
    assert "class_members" in sql and "c.teacher_id = $2" in sql


@pytest.fixture
def classes(monkeypatch):
    async def link(code):
        return f"https://t.me/bot?start=class_{code}"

    monkeypatch.setattr(classwork, "_class_link", link)
    return lambda count: fake(monkeypatch, "teacher_classes", [None] * count)


def test_anyone_creates_a_class(monkeypatch, classes):
    classes(0)
    created = fake(monkeypatch, "create_class", {"id": 1, "name": "5Б", "code": "abc", "members": 0})
    out = asyncio.run(classwork.post_class(schemas.ClassIn(name=" 5Б "), REQUEST, 42))
    assert out.name == "5Б"
    assert created[0][:2] == (42, "5Б")


def test_classes_are_capped(monkeypatch, classes):
    classes(classwork.MAX_CLASSES)
    created = fake(monkeypatch, "create_class", None)
    assert status_of(classwork.post_class(schemas.ClassIn(name="21-й"), REQUEST, 42)) == 409
    assert created == []


def test_group_of_another_teacher_cannot_be_rebound(monkeypatch):
    fake(monkeypatch, "chat_class", {"id": 3, "name": "5Б", "teacher_id": 7, "assistant": False})
    bound = fake(monkeypatch, "bind_chat", None)
    assert status_of(groups.bind(-100, schemas.BindIn(title="5Б"), REQUEST, 42)) == 403
    assert bound == []
