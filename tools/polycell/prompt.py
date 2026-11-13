"""Buduje kompletny, samowystarczalny prompt do wygenerowania JEDNEJ komórki przez LLM.

  python tools/polycell/prompt.py pricing.quote [--fix]  > prompt.md
Zasada: LLM generuje cały plik od nowa (regeneracja zamiast refaktoryzacji). Kontekst = tylko kontrakt,
typy i przykłady - nie cały projekt - więc prompt jest mały i powtarzalny.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from model import ROOT, load_cells  # noqa: E402

RULES = {
    "python": """- Python 3.12, tylko biblioteka standardowa.
- Pierwsza linia DOKŁADNIE: `# polycell: urn={urn} contract={h}`
- Import typów: `from polycell_types import {P}Input, {P}Output`
- Eksportuj `def run(input: {P}Input) -> {P}Output:`; wejście/wyjście to zwykłe dict-y.""",
    "ts": """- TypeScript uruchamiany przez Node 22 z usuwaniem typów: tylko składnia usuwalna (bez enum, namespace, parameter properties).
- Pierwsza linia DOKŁADNIE: `// polycell: urn={urn} contract={h}`
- `import type {{ {P}Input, {P}Output }} from "../../gen/ts/types.ts";`
- Eksportuj `export function run(input: {P}Input): {P}Output`. Bez zależności npm.""",
    "rust": """- Rust 2021, tylko std (+ serde_json dostępny). Plik jest wstawiany do modułu przez include!().
- Pierwsza linia DOKŁADNIE: `// polycell: urn={urn} contract={h}`
- `use crate::types::*;` i `pub fn run(input: {P}Input) -> Result<{P}Output, String>`.
- Bez `mod`, bez `//!`, bez `unsafe`, bez I/O.""",
}


def type_excerpt(c) -> str:
    gen = {"python": ROOT / "gen/python/polycell_types.py", "ts": ROOT / "gen/ts/types.ts",
           "rust": ROOT / "gen/rust/types.rs"}[c.owner].read_text()
    names = [f"{c.pascal}Input", f"{c.pascal}Output", *c.types]
    blocks = re.split(r"\n\s*\n", gen)
    return "\n\n".join(b.strip() for b in blocks if any(re.search(rf"\b(class|interface|struct) {n}\b", b) for n in names))


def build(name: str, fix: bool = False) -> str:
    c = next((x for x in load_cells() if x.name == name), None)
    if not c:
        raise SystemExit(f"unknown cell {name}")
    rules = RULES[c.owner].format(urn=c.urn, h=c.interface_hash, P=c.pascal)
    contract = c.path.read_text(encoding="utf-8")
    current = c.cell_path.read_text(encoding="utf-8") if c.cell_path.exists() else "(brak)"
    golden = ROOT / "tests/golden" / f"{c.name}.jsonl"
    gold = golden.read_text(encoding="utf-8")[:4000] if golden.exists() else ""
    parts = [
        f"# Zadanie: wygeneruj komórkę `{c.name}` ({c.owner})",
        "Napisz CAŁY plik od nowa. Zwróć wyłącznie zawartość pliku w jednym bloku kodu, bez komentarza.",
        f"Ścieżka pliku: `{c.cell_path.relative_to(ROOT)}`",
        "## Reguły", rules,
        "- Funkcja czysta: bez sieci, plików, bazy, zmiennych globalnych ze stanem, logowania (to robią hosty).",
        "- Błędy domenowe: Python/TS rzuć wyjątek, Rust zwróć Err(String). Nie zmieniaj kształtu wyjścia.",
        "- Wynik MUSI przejść wszystkie przykłady i przypadki golden poniżej (porównanie dokładne, float do 1e-9).",
        "## Kontrakt (źródło prawdy)", f"```yaml\n{contract}```",
        "## Wygenerowane typy (nie edytuj, tylko używaj)", f"```\n{type_excerpt(c)}\n```",
    ]
    if gold:
        parts += ["## Przypadki golden z produkcji (legacy) - muszą dawać identyczny wynik", f"```jsonl\n{gold}```"]
    if fix:
        parts += ["## Obecna implementacja (do zastąpienia w całości)", f"```\n{current}\n```"]
    parts += ["## Weryfikacja po zapisaniu pliku", "`make check && make parity` - komórka jest gotowa, gdy oba przechodzą."]
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: prompt.py <cell.name> [--fix]")
    print(build(sys.argv[1], "--fix" in sys.argv))
