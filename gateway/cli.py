"""CLI (ten sam rdzeń co REST/MCP):

  python -m gateway.cli call pricing.quote '{"items":[{"sku":"A","qty":1,"unit_price":10}],"currency":"PLN"}' [--transport http]
  python -m gateway.cli process checkout @tests/input.json
  python -m gateway.cli nl "policz cenę koszyka"
  python -m gateway.cli parity
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import core


def _arg(s: str):
    return json.loads(Path(s[1:]).read_text() if s.startswith("@") else s)


def main():
    ap = argparse.ArgumentParser(prog="polycell")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("call"); c.add_argument("cell"); c.add_argument("json"); c.add_argument("--transport")
    p = sub.add_parser("process"); p.add_argument("name"); p.add_argument("json"); p.add_argument("--transport")
    n = sub.add_parser("nl"); n.add_argument("text")
    sub.add_parser("parity")
    a = ap.parse_args()
    if a.cmd == "call":
        out = core.invoke(a.cell, _arg(a.json), a.transport)
    elif a.cmd == "process":
        out = core.run_process(a.name, _arg(a.json), a.transport)
    elif a.cmd == "nl":
        out = core.nl_match(a.text)
    else:
        out = core.parity()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if out.get("ok", out.get("all_ok", True)) else 1)


if __name__ == "__main__":
    main()
