#!/usr/bin/env python3
"""Сверяет .env с .env.example: новый ключ, забытый в .env, на новой машине
превращается в молчаливый дефолт, который всплывёт через месяц."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def keys(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        result[name.strip()] = value.strip()
    return result


def main() -> int:
    example = ROOT / ".env.example"
    env = ROOT / ".env"
    if not env.exists():
        print(f"нет {env}: скопируй .env.example и заполни", file=sys.stderr)
        return 1

    expected, actual = keys(example), keys(env)

    missing = sorted(set(expected) - set(actual))
    # Пустое значение в шаблоне — «заполнить обязательно».
    empty = sorted(k for k, v in expected.items() if not v and not actual.get(k))

    for name in missing:
        print(f"нет ключа {name}", file=sys.stderr)
    for name in empty:
        print(f"ключ {name} обязателен и пуст", file=sys.stderr)

    if missing or empty:
        return 1
    print("env ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
