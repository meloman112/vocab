#!/usr/bin/env python3
"""Печатает букмарклет с подставленными адресом и токеном из .env.

Готовой строки в репозитории нет намеренно: в неё пришлось бы вписать
боевой токен.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = (
    "javascript:(()=>{{const w=getSelection().toString().trim();"
    "if(!w)return alert('ничего не выделено');"
    "fetch('https://{host}/words',{{method:'POST',"
    "headers:{{'Content-Type':'application/json','X-Token':'{token}'}},"
    "body:JSON.stringify({{word:w,source_url:location.href}})}})"
    ".then(r=>r.ok?r.json():Promise.reject(r.status))"
    ".then(c=>alert(c.created?'✅ '+c.word:'уже есть: '+c.word))"
    ".catch(e=>alert('vocab: ошибка '+e));}})()"
)


def env() -> dict[str, str]:
    path = ROOT / ".env"
    if not path.exists():
        print("нет .env", file=sys.stderr)
        raise SystemExit(1)
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


if __name__ == "__main__":
    cfg = env()
    print(TEMPLATE.format(host=cfg["DOMAIN"], token=cfg["API_TOKEN"]))
