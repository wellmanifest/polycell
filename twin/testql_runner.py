"""Bezzależnościowy runner podzbioru TestTOON (autogrammar/testql): CONFIG / API / ASSERT.
Rozszerzenie: opcjonalna 4. kolumna `body` (JSON) w bloku API. ASSERT sprawdza ostatnią odpowiedź.
Jeśli zainstalowany jest prawdziwy `testql`, Makefile używa go do plików zgodnych (smoke).

  python twin/testql_runner.py tests/generated/*.testql.toon.yaml --url http://localhost:8080
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

OPS = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b, ">": lambda a, b: a > b,
       "contains": lambda a, b: b in a}


def parse(text: str) -> dict:
    blocks, cur = {}, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\w+)\[\d+\]\{([^}]*)\}:\s*$", line)
        if m:
            cur = m[1]
            blocks[cur] = {"cols": [c.strip() for c in m[2].split(",")], "rows": []}
        elif cur:
            cols = blocks[cur]["cols"]
            blocks[cur]["rows"].append([c.strip() for c in line.strip().split(",", len(cols) - 1)])
    return blocks


def get_path(obj, path: str):
    for part in path.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


def run(file: str, base: str) -> bool:
    b = parse(open(file, encoding="utf-8").read())
    ok, last = True, None
    for row in b.get("API", {}).get("rows", []):
        method, endpoint, status = row[0], row[1], int(row[2])
        body = row[3] if len(row) > 3 and row[3] not in ("-", "") else None
        req = urllib.request.Request(base + endpoint, method=method, data=body.encode() if body else None,
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                code, payload = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, payload = e.code, e.read()
        try:
            last = json.loads(payload)
        except ValueError:
            last = payload.decode(errors="replace")
        good = code == status
        ok &= good
        print(f"  {'✓' if good else '✗'} {method} {endpoint} -> {code} (expected {status})")
    for field, op, expected in b.get("ASSERT", {}).get("rows", []):
        actual = get_path(last, field)
        exp = json.loads(expected)
        good = OPS[op](actual, exp)
        ok &= good
        print(f"  {'✓' if good else '✗'} {field} {op} {expected} (actual {json.dumps(actual, ensure_ascii=False)})")
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    url = "http://localhost:8080"
    if "--url" in args:
        i = args.index("--url")
        url = args[i + 1]
        del args[i:i + 2]
    results = []
    for f in args:
        print(f"SCENARIO {f}")
        results.append(run(f, url.rstrip("/")))
    print(f"{sum(results)}/{len(results)} scenarios passed")
    sys.exit(0 if all(results) else 1)
