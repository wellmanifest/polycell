"""Model kontraktów polycell: ładowanie, typy, hash interfejsu.

Jedno źródło prawdy (contracts/**/*.yaml) -> wszystko inne jest generowane.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCALARS = {"string", "int32", "int64", "double", "bool", "json"}
LANG_EXT = {"python": "py", "ts": "ts", "rust": "rs"}
URN_RE = re.compile(r"^urn:wm:cell:(?P<ns>[a-z0-9_-]+):(?P<name>[a-z0-9_.]+):v(?P<major>[0-9]+)$")


@dataclass
class TypeRef:
    base: str
    is_list: bool = False
    optional: bool = False

    @classmethod
    def parse(cls, raw: str) -> "TypeRef":
        raw = str(raw).strip()
        optional = raw.endswith("?")
        raw = raw.rstrip("?")
        is_list = raw.endswith("[]")
        return cls(raw[:-2] if is_list else raw, is_list, optional)

    @property
    def scalar(self) -> bool:
        return self.base in SCALARS


@dataclass
class Cell:
    path: Path
    raw: dict
    urn: str
    name: str
    owner: str
    input: dict[str, TypeRef]
    output: dict[str, TypeRef]
    types: dict[str, dict[str, TypeRef]] = field(default_factory=dict)

    @property
    def ns(self) -> str:
        return URN_RE.match(self.urn)["ns"]

    @property
    def major(self) -> str:
        return URN_RE.match(self.urn)["major"]

    @property
    def snake(self) -> str:
        return self.name.replace(".", "_")

    @property
    def pascal(self) -> str:
        return "".join(p[:1].upper() + p[1:] for p in re.split(r"[._]", self.name))

    @property
    def cell_path(self) -> Path:
        return ROOT / "cells" / self.owner / f"{self.snake}.{LANG_EXT[self.owner]}"

    @property
    def interface_hash(self) -> str:
        """Hash tylko tego, co dotyczy interfejsu. Zmiana opisu/NL/menu nie unieważnia logiki."""
        keys = ("urn", "owner", "input", "output", "types", "effects")
        canon = json.dumps({k: self.raw.get(k) for k in keys}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canon.encode()).hexdigest()[:12]


def _fields(d: dict | None) -> dict[str, TypeRef]:
    return {k: TypeRef.parse(v) for k, v in (d or {}).items()}


def load_cells(root: Path = ROOT) -> list[Cell]:
    cells = []
    for p in sorted((root / "contracts" / "cells").glob("*.cell.yaml")):
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        cells.append(Cell(
            path=p, raw=raw, urn=raw["urn"], name=raw["name"], owner=raw["owner"],
            input=_fields(raw.get("input")), output=_fields(raw.get("output")),
            types={t: _fields(f) for t, f in (raw.get("types") or {}).items()},
        ))
    return cells


def load_processes(root: Path = ROOT) -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted((root / "contracts" / "processes").glob("*.process.yaml"))]


def all_types(cells: list[Cell]) -> dict[str, dict[str, TypeRef]]:
    out: dict[str, dict[str, TypeRef]] = {}
    for c in cells:
        for t, f in c.types.items():
            out[t] = f
    return out


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else ""


HEADER_RE = re.compile(r"polycell:\s*urn=(?P<urn>\S+)\s+contract=(?P<hash>[0-9a-f]{12})")


def read_header(path: Path) -> dict | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines()[:5]:
        m = HEADER_RE.search(line)
        if m:
            return m.groupdict()
    return None
