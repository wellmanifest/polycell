#!/usr/bin/env python3
"""wellmanifest/polycell v1 - kontrola zgodności (wymaga tylko PyYAML do czytania kontraktów).

Wynik w formacie zgodnym z wellman ConformanceRunner: findings[{code, severity, message}].
  python standard/conformance.py --root . [--json]
Kody: PC001..PC010 (opis w docs/SPEC.md). Exit 1, gdy jest jakikolwiek błąd (severity=error).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.polycell.guards import parse_guard

URN = re.compile(r"^urn:wm:cell:(?P<ns>[a-z0-9_-]+):(?P<name>[a-z0-9_.]+):v(?P<major>[0-9]+)$")
LANGS = {"python": "py", "ts": "ts", "rust": "rs"}
SCALARS = {"string", "int32", "int64", "double", "bool", "json"}
EFFECTS = {"pure", "read_data", "write_data", "local_write", "external", "credential_use"}
HEADER = re.compile(r"polycell:\s*urn=(?P<urn>\S+)\s+contract=(?P<hash>[0-9a-f]{12})")
IMPURE = {  # zakazane w komórkach z effects=[pure]; transport i I/O należą do hostów
    "py": re.compile(r"^\s*(import|from)\s+(socket|subprocess|requests|httpx|urllib|psycopg|sqlite3|grpc)\b|os\.system|open\(", re.M),
    "ts": re.compile(r"from\s+\"node:(fs|net|http|child_process)\"|\bfetch\(|require\(", re.M),
    "rs": re.compile(r"std::(net|fs|process)|reqwest|tokio::net", re.M),
}


def interface_hash(raw: dict) -> str:
    keys = ("urn", "owner", "input", "output", "types", "effects")
    return hashlib.sha256(json.dumps({k: raw.get(k) for k in keys}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def run(root: Path) -> list[dict]:
    f: list[dict] = []

    def add(code, sev, msg):
        f.append({"code": code, "severity": sev, "message": msg})

    contracts = {}
    types_seen: dict[str, tuple[str, dict]] = {}
    for p in sorted((root / "contracts/cells").glob("*.cell.yaml")):
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        rel = p.relative_to(root)
        missing = [k for k in ("schema", "urn", "name", "owner", "input", "output") if k not in raw]
        if missing or raw.get("schema") != "wellmanifest.polycell.cell/v1":
            add("PC001", "error", f"{rel}: invalid contract header (missing={missing}, schema={raw.get('schema')})")
            continue
        m = URN.match(raw["urn"])
        if not m or m["name"] != raw["name"]:
            add("PC001", "error", f"{rel}: urn {raw['urn']} does not match name {raw['name']}")
        if raw["owner"] not in LANGS:
            add("PC001", "error", f"{rel}: owner must be one of {sorted(LANGS)}")
            continue
        for e in raw.get("effects") or []:
            if e not in EFFECTS:
                add("PC001", "error", f"{rel}: unknown effect {e}")
        if raw["urn"] in contracts:
            add("PC002", "error", f"duplicate urn {raw['urn']}")
        known = SCALARS | set((raw.get("types") or {}))
        for t, fields in (raw.get("types") or {}).items():
            if t in types_seen and types_seen[t][1] != fields:
                add("PC002", "error", f"type {t} defined differently in {types_seen[t][0]} and {rel}")
            types_seen[t] = (str(rel), fields)
        for sect in ("input", "output"):
            for k, v in (raw.get(sect) or {}).items():
                base = str(v).rstrip("?").removesuffix("[]")
                if base not in known and base not in types_seen:
                    add("PC001", "error", f"{rel}: {sect}.{k} unknown type {v}")
        contracts[raw["urn"]] = (rel, raw)

    expected_cells = set()
    for urn, (rel, raw) in contracts.items():
        ext = LANGS[raw["owner"]]
        cell = root / "cells" / raw["owner"] / f"{raw['name'].replace('.', '_')}.{ext}"
        expected_cells.add(cell.resolve())
        if not cell.exists():
            add("PC003", "error", f"GAP: {urn} has no implementation ({cell.relative_to(root)})")
            continue
        text = cell.read_text(encoding="utf-8")
        h = next((HEADER.search(l) for l in text.splitlines()[:5] if HEADER.search(l)), None)
        if not h or h["urn"] != urn:
            add("PC003", "error", f"{cell.relative_to(root)}: missing/mismatched polycell header")
        elif h["hash"] != interface_hash(raw):
            add("PC003", "error", f"STALE: {cell.relative_to(root)} implements contract {h['hash']}, current {interface_hash(raw)} -> make prompt CELL={raw['name']}")
        if "generate me" in text:
            add("PC003", "warning", f"STUB: {cell.relative_to(root)} not implemented yet")
        if (raw.get("effects") or ["pure"]) == ["pure"] and IMPURE[ext].search(text):
            add("PC008", "error", f"{cell.relative_to(root)}: I/O or transport inside a pure cell")
        if not raw.get("examples"):
            add("PC005", "warning", f"{urn}: no examples -> no contract tests")
        for r in raw.get("replaces") or []:
            if raw.get("impl", "cell") == "cell" and (root / r.split(":")[0]).exists():
                add("PC009", "warning", f"{urn}: replaced legacy code still present: {r} (make prune)")

    for lang, ext in LANGS.items():
        for cell in (root / "cells" / lang).glob(f"*.{ext}"):
            if cell.resolve() not in expected_cells:
                add("PC004", "error", f"ORPHAN: {cell.relative_to(root)} has no contract (dead code or missing contract)")

    for p in sorted((root / "contracts/processes").glob("*.process.yaml")):
        proc = yaml.safe_load(p.read_text(encoding="utf-8"))
        ids = set()
        if proc.get("schema") != "poa.process/v1" or not str(proc.get("process_ref", "")).startswith("poa://"):
            add("PC006", "error", f"{p.name}: schema must be poa.process/v1 and process_ref poa://...")
        for s in proc.get("steps", []):
            step_id = s.get("id")
            if not isinstance(step_id, str) or not step_id or step_id in ids:
                add("PC006", "error", f"{p.name}: invalid or duplicate step id: {step_id}")
                continue
            if "guard" in s:
                try:
                    parse_guard(s["guard"])
                except ValueError as error:
                    add("PC006", "error", f"{p.name}: invalid guard at {s['id']}: {error}")
            if s["capability_ref"] not in contracts:
                add("PC006", "error", f"{p.name}: step {s['id']} references unknown capability {s['capability_ref']}")
            for d in s.get("depends_on", []):
                if d not in ids:
                    add("PC006", "error", f"{p.name}: step {s['id']} depends on unknown/later step {d}")
            if any(k in json.dumps(s) for k in ("http://", "grpc://", "https://")):
                add("PC006", "error", f"{p.name}: step {s['id']} contains a transport address (only URNs allowed)")
            if s.get("kind") == "query" and set(s.get("effects", [])) - {"read_data", "pure"}:
                add("PC006", "error", f"{p.name}: query step {s['id']} declares mutating effects")
            ids.add(s["id"])

    reg = root / "gen/registry.json"
    if not reg.exists() or json.loads(reg.read_text()).get("schema") != "wellmanifest.api-registry/v1":
        add("PC007", "error", "gen/registry.json missing or not wellmanifest.api-registry/v1 (run make gen)")
    lock = root / "contracts/polycell.lock.json"
    if lock.exists():
        locked = json.loads(lock.read_text())["cells"]
        for urn, (_, raw) in contracts.items():
            if locked.get(urn, {}).get("contract") != interface_hash(raw):
                add("PC007", "error", f"{urn}: generated artifacts out of date (run make gen)")
    else:
        add("PC007", "error", "contracts/polycell.lock.json missing (run make gen)")
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings = run(Path(a.root).resolve())
    errors = [x for x in findings if x["severity"] == "error"]
    if a.json:
        print(json.dumps({"standard": "wellmanifest/polycell", "version": "1.0.0", "ok": not errors, "findings": findings}, indent=2))
    else:
        for x in findings:
            print(f"{x['severity'].upper():7} {x['code']} {x['message']}")
        print(f"polycell conformance: {'PASS' if not errors else 'FAIL'} ({len(errors)} errors, {len(findings) - len(errors)} warnings)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
