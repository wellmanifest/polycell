"""Adopcja polycell w istniejącym projekcie (wzorzec strangler fig) - bez przepisywania wszystkiego naraz.

  inventory --map map.toon.yaml | --src DIR   ranking kandydatów na komórki (czyste funkcje, hotspoty)
  wrap --func path.py:fn --name ns.cell       kontrakt + komórka-shim delegująca do starego kodu (interfejsy działają od razu)
  golden <cell>                               zrzut realnych wywołań z DB (wm_invocations) -> tests/golden/<cell>.jsonl
  switch <cell>                               po regeneracji: impl legacy -> cell (wymaga zielonego parity na golden)
  prune <cell> [--apply]                      usuń zastąpiony stary kod (tylko gdy nie ma już odwołań)
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from model import ROOT, load_cells  # noqa: E402

PURE_VERB = re.compile(r"^(validate|parse|normalize|normalise|compute|calc|calculate|render|format|digest|canonical|evaluate|"
                       r"reconcile|score|match|classify|convert|to_|from_|build_|derive|merge|diff|plan|select|rank|resolve|"
                       r"encode|decode|serialize|deserialize|compare|summari[sz]e|extract|transform|map_|filter_)")
IO_VERB = re.compile(r"^(main|run|load_|read_|write_|save_|git_|fetch|post|get_|open|start|stop|serve|install|publish|print)")
SKIP_DIRS = frozenset({
    ".git", ".worktrees", "worktrees", ".governance", ".subactor",
    ".venv", "venv", "build", "dist", "gen", ".run", "__pycache__",
    "test", "tests", "benchmark", "benchmarks", "example", "examples",
    "vendor", "site-packages", "node_modules", "templates", "migrations",
})
SKIP = re.compile(
    r"(^|/)(\.git|\.worktrees|worktrees|\.governance|\.subactor|\.venv|venv|build|dist|gen|\.run|__pycache__|"
    r"[^/]+\.egg-info|tests?|benchmarks?|examples?|vendor|site-packages|node_modules|templates|migrations)(/|$)|(^|/)test_"
)
IMPURE_CALLS = {"open", "print", "input", "exec", "eval"}
IMPURE_MODS = {"os", "sys", "subprocess", "socket", "requests", "httpx", "urllib", "shutil", "sqlite3", "psycopg", "time"}


def _cell_name(path: str, fn: str) -> str:
    stem = Path(path).stem.lower().replace("-", "_")
    return f"{stem}.{fn.lower()}"


def _score(path: str, fn: str, nargs: int, lines: int, cc: int = 0, impure: bool | None = None) -> float:
    s = 3.0 if PURE_VERB.match(fn) else 0.0
    s -= 4.0 if IO_VERB.match(fn) or fn.startswith("_") else 0.0
    s += 1.0 if 1 <= nargs <= 4 else (-1.0 if nargs > 6 else 0)
    s += 1.0 if cc >= 8 else 0.0          # złożona logika = najwięcej zysku z regeneracji + testów
    s -= 5.0 if impure else 0.0
    s += 2.0 if impure is False else 0.0  # AST potwierdził brak I/O (tryb --src)
    s -= 0.5 if lines > 1500 else 0.0     # gigantyczne moduły najpierw dzielimy
    return s


def inventory_map(path: Path) -> dict:
    """Parser formatu code2llm map.toon.yaml (sekcje M: i D:)."""
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header = [l for l in text[:12] if l.startswith("#")]
    lines_of, funcs, cur, section = {}, [], None, None
    for l in text:
        if re.match(r"^M\[\d+\]:", l):
            section = "M"; continue
        if l.startswith("D:"):
            section = "D"; continue
        if section == "M":
            m = re.match(r"^  (.+),(\d+)$", l)
            if m:
                lines_of[m[1]] = int(m[2])
        elif section == "D":
            m = re.match(r"^  (\S.*):$", l)
            if m:
                cur = m[1]; continue
            m = re.match(r"^    ([A-Za-z_]\w*)\((.*)\)\s*$", l)
            if cur and m and not SKIP.search(cur) and cur.endswith((".py", ".rs")):
                args = [a for a in m[2].split(";") if a and a not in ("self", "cls")]
                funcs.append({"file": cur, "function": m[1], "args": args, "module_lines": lines_of.get(cur, 0)})
    for f in funcs:
        f["score"] = _score(f["file"], f["function"], len(f["args"]), f["module_lines"])
        f["suggested_cell"] = _cell_name(f["file"], f["function"])
        f["owner"] = "rust" if f["file"].endswith(".rs") else "python"
    return {"source": str(path), "header": header, "functions_seen": len(funcs), "candidates": funcs}


def _cc(node) -> int:
    return 1 + sum(isinstance(n, (ast.If, ast.For, ast.While, ast.BoolOp, ast.ExceptHandler, ast.IfExp, ast.comprehension, ast.Match))
                   for n in ast.walk(node))


def _impure(node) -> bool:
    for n in ast.walk(node):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            return True
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id in IMPURE_CALLS:
                return True
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in IMPURE_MODS:
                return True
    return False


def _iter_source_py_files(src: Path):
    for root, dirs, files in os.walk(src):
        dirs[:] = [
            d for d in sorted(dirs)
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]
        for fname in sorted(files):
            if not fname.endswith(".py") or fname.startswith("test_"):
                continue
            full = Path(root) / fname
            rel = full.relative_to(src).as_posix()
            if not SKIP.search(rel):
                yield full, rel


def inventory_src(src: Path) -> dict:
    funcs = []
    for p, rel in _iter_source_py_files(src):
        try:
            source_text = p.read_text(encoding="utf-8")
            tree = ast.parse(source_text)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        nlines = len(source_text.splitlines())
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                args = [a.arg for a in n.args.args if a.arg not in ("self", "cls")]
                cc, imp = _cc(n), _impure(n)
                funcs.append({"file": rel, "function": n.name, "args": args, "cc": cc, "pure_guess": not imp,
                              "module_lines": nlines, "score": _score(rel, n.name, len(args), nlines, cc, imp),
                              "suggested_cell": _cell_name(rel, n.name), "owner": "python"})
    return {"source": str(src), "functions_seen": len(funcs), "candidates": funcs}


def cmd_inventory(a) -> None:
    inv = inventory_map(Path(a.map)) if a.map else inventory_src(Path(a.src))
    inv["candidates"].sort(key=lambda f: -f["score"])
    per_module: Counter = Counter()
    top = []
    for c in inv["candidates"]:  # max 3 na moduł -> szerszy obraz projektu
        if c["score"] >= 3 and per_module[c["file"]] < 3:
            per_module[c["file"]] += 1
            top.append(c)
    top = top[: a.top]
    by_module = Counter(c["file"] for c in top)
    out = ROOT / "adoption"
    out.mkdir(exist_ok=True)
    (out / "candidates.json").write_text(json.dumps({**inv, "candidates": top}, indent=2, ensure_ascii=False))
    md = [f"# Kandydaci na komórki polycell\n\nŹródło: `{inv['source']}` · funkcji przeanalizowanych: {inv['functions_seen']}\n"]
    md += [f"    {h}" for h in inv.get("header", [])]
    md += ["\n## Kolejność migracji (moduły z największą liczbą czystych funkcji)\n"]
    md += [f"{i}. `{m}` - {n} kandydatów" for i, (m, n) in enumerate(by_module.most_common(10), 1)]
    names = Counter(c["function"] for c in inv["candidates"] if c["score"] >= 2)
    dups = [(n, k) for n, k in names.most_common(15) if k >= 3]
    if dups:
        md += ["\n## Duplikaty: jedna komórka zastąpi N kopii (największy zysk, najmniejsze ryzyko)\n"]
        md += [f"- `{n}` - {k} implementacji w różnych modułach" for n, k in dups]
    md += ["\n## Top kandydaci\n", "| score | plik | funkcja | argumenty | proponowana komórka |", "|---|---|---|---|---|"]
    md += [f"| {c['score']:.1f} | `{c['file']}` | `{c['function']}` | {', '.join(c['args'])} | `{c['suggested_cell']}` |" for c in top]
    md += ["\nNastępny krok: `make wrap FUNC=<plik>:<funkcja> CELL=<komórka>` dla 3-5 pierwszych pozycji."]
    (out / "candidates.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(top)} candidates -> adoption/candidates.md")


PY_TYPES = {"str": "string", "int": "int64", "float": "double", "bool": "bool"}


def cmd_wrap(a) -> None:
    file, fn = a.func.split(":")
    legacy_root = Path(os.environ.get("LEGACY_ROOT", ".")).resolve()
    src = legacy_root / file
    tree = ast.parse(src.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn)
    inp = {}
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        ann = ast.unparse(arg.annotation) if arg.annotation else ""
        inp[arg.arg] = PY_TYPES.get(ann, "json")
    ns = a.ns
    contract = {
        "schema": "wellmanifest.polycell.cell/v1", "urn": f"urn:wm:cell:{ns}:{a.name}:v1", "name": a.name,
        "version": "0.1.0", "owner": "python", "summary": (ast.get_docstring(node) or f"legacy {file}:{fn}").splitlines()[0],
        "effects": ["read_data"], "impl": "legacy", "replaces": [f"{file}:{fn}"],
        "input": inp or {"payload": "json"}, "output": {"result": "json"},
        "nl": {"pl": [fn.replace("_", " ")], "en": [fn.replace("_", " ")]},
        "menu": {"category": "Legacy", "label": fn, "interactionType": "modal_form"}, "examples": [],
    }
    cpath = ROOT / "contracts/cells" / f"{a.name}.cell.yaml"
    cpath.write_text("# Kontrakt wygenerowany przez adopt.py wrap - uzupełnij typy wyjścia i przykłady.\n"
                     + yaml.safe_dump(contract, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cell = next(c for c in load_cells() if c.name == a.name)
    cell.cell_path.write_text(f'''# polycell: urn={cell.urn} contract={cell.interface_hash}
# LEGACY SHIM (strangler fig): deleguje do istniejącego kodu {file}:{fn}.
# Interfejsy (REST/gRPC/MCP/CLI/UI) i zapis do DB działają od razu; logikę regenerujemy później.
import importlib.util
import os
from pathlib import Path

_SRC = Path(os.environ.get("LEGACY_ROOT", {str(legacy_root)!r})) / {file!r}
_spec = importlib.util.spec_from_file_location("legacy_{cell.snake}", _SRC)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def run(input):
    return {{"result": _mod.{fn}(**input)}}
''', encoding="utf-8")
    print(f"wrapped {file}:{fn} -> {cpath.relative_to(ROOT)} + {cell.cell_path.relative_to(ROOT)}\n"
          f"next: make gen && (używaj przez API) && make golden CELL={a.name} && make prompt CELL={a.name}")


def cmd_golden(a) -> None:
    cell = next(c for c in load_cells() if c.name == a.cell)
    app = os.environ.get("APP_URL", "http://127.0.0.1:8080")
    try:  # przez gateway (PGlite ma jedno połączenie, które trzyma gateway)
        import urllib.parse
        import urllib.request
        with urllib.request.urlopen(f"{app}/api/export?urn={urllib.parse.quote(cell.urn)}", timeout=10) as r:
            rows = json.loads(r.read())
    except OSError:
        sys.path.insert(0, str(ROOT))
        from gateway.db import DB
        rows = DB().query("select input, output from wm_invocations where urn = ? and ok = ? order by id", (cell.urn, True))
    seen, out = set(), []
    for r in rows:
        i = r["input"] if isinstance(r["input"], dict) else json.loads(r["input"])
        o = r["output"] if isinstance(r["output"], dict) else json.loads(r["output"])
        key = json.dumps(i, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(json.dumps({"input": i, "output": o}, ensure_ascii=False))
    p = ROOT / "tests/golden" / f"{cell.name}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(out)} golden cases -> {p.relative_to(ROOT)} (make gen dołączy je do testów parity)")


def _set_impl(name: str, impl: str) -> None:
    p = ROOT / "contracts/cells" / f"{name}.cell.yaml"
    t = p.read_text(encoding="utf-8")
    p.write_text(re.sub(r"^impl: \w+", f"impl: {impl}", t, flags=re.M), encoding="utf-8")


def cmd_switch(a) -> None:
    r = subprocess.run([sys.executable, "-m", "gateway.cli", "parity"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0 or '"all_ok": true' not in r.stdout:
        raise SystemExit("parity failed - nowa komórka nie odtwarza zachowania legacy; nie przełączam\n" + r.stdout[-2000:])
    _set_impl(a.cell, "cell")
    print(f"{a.cell}: impl=cell. Teraz: make prune CELL={a.cell}")


def cmd_prune(a) -> None:
    cell = next(c for c in load_cells() if c.name == a.cell)
    if cell.raw.get("impl", "cell") != "cell":
        raise SystemExit("najpierw: adopt.py switch (impl musi być 'cell')")
    legacy_root = Path(os.environ.get("LEGACY_ROOT", ".")).resolve()
    for ref in cell.raw.get("replaces") or []:
        file, fn = ref.split(":")
        src = legacy_root / file
        node = next(n for n in ast.parse(src.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == fn)
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        refs = subprocess.run(["grep", "-rnw", "--include=*.py", fn, str(legacy_root)], capture_output=True, text=True).stdout
        others = []
        for l in refs.splitlines():
            path, lineno = l.split(":", 2)[:2]
            if "/cells/" in path or (Path(path) == src and start <= int(lineno) <= node.end_lineno):
                continue  # sama definicja lub nasza komórka
            others.append(l)
        print(f"{ref}: {len(others)} odwołań poza definicją")
        for l in others[:20]:
            print("   ", l)
        if others or not a.apply:
            continue
        lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
        del lines[start - 1:node.end_lineno]
        src.write_text("".join(lines), encoding="utf-8")
        print(f"   usunięto {fn} z {file} (linie {start}-{node.end_lineno})")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inventory"); i.add_argument("--map"); i.add_argument("--src"); i.add_argument("--top", type=int, default=40)
    w = sub.add_parser("wrap"); w.add_argument("--func", required=True); w.add_argument("--name", required=True); w.add_argument("--ns", default="legacy")
    g = sub.add_parser("golden"); g.add_argument("cell")
    s = sub.add_parser("switch"); s.add_argument("cell")
    p = sub.add_parser("prune"); p.add_argument("cell"); p.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    {"inventory": cmd_inventory, "wrap": cmd_wrap, "golden": cmd_golden, "switch": cmd_switch, "prune": cmd_prune}[a.cmd](a)


if __name__ == "__main__":
    main()
