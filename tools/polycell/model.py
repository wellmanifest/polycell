"""Model kontraktów polycell: ładowanie, typy, hash interfejsu.

Jedno źródło prawdy (contracts/**/*.yaml) -> wszystko inne jest generowane.
"""
from __future__ import annotations

import hashlib
import json
import keyword
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCALARS = {"string", "int32", "int64", "double", "bool", "json"}
LANG_EXT = {"python": "py", "ts": "ts", "rust": "rs"}
URN_RE = re.compile(r"^urn:wm:cell:(?P<ns>[a-z0-9_-]+):(?P<name>[a-z0-9_.]+):v(?P<major>[0-9]+)$")
RUST_KEYWORDS = set("""as break const continue crate else enum extern false fn for if impl in let
loop match mod move mut pub ref return self Self static struct super trait true type unsafe
use where while async await dyn abstract become box do final gen macro override priv try
typeof unsized virtual yield""".split())


def portable_identifier(name: str) -> None:
    # Every contract emits Python and Rust types, regardless of its cell owner.
    if not name.isidentifier() or keyword.iskeyword(name) or name in RUST_KEYWORDS:
        raise ValueError(f"not a portable identifier: {name}")


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
    root: Path = ROOT

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
        return self.root / "cells" / self.owner / f"{self.snake}.{LANG_EXT[self.owner]}"

    @property
    def interface_hash(self) -> str:
        """Hash tylko tego, co dotyczy interfejsu. Zmiana opisu/NL/menu nie unieważnia logiki."""
        keys = ("urn", "owner", "input", "output", "types", "effects")
        canon = json.dumps({k: self.raw.get(k) for k in keys}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canon.encode()).hexdigest()[:12]


def _fields(d: dict | None) -> dict[str, TypeRef]:
    return {k: TypeRef.parse(v) for k, v in (d or {}).items()}


def validate_contract_set(contracts: list[dict]) -> None:
    """Reject ambiguous symbols before generation can overwrite existing artifacts."""
    validator = Draft202012Validator(json.loads((ROOT / "standard/polycell-cell.schema.v1.json").read_text()))
    seen = {key: set() for key in ("urn", "name", "filename", "type")}
    types = {}
    for raw in contracts:
        validator.validate(raw)
        if URN_RE.fullmatch(raw["urn"])["name"] != raw["name"]:
            raise ValueError("contract name does not match URN")
        symbols = {"urn": raw["urn"], "name": raw["name"], "filename": raw["name"].replace(".", "_"),
                   "type": "".join(p[:1].upper() + p[1:] for p in re.split(r"[._]", raw["name"]))}
        portable_identifier(symbols["filename"])
        portable_identifier(symbols["type"])
        for key, symbol in symbols.items():
            if symbol in seen[key]:
                raise ValueError(f"duplicate {key}: {symbol}; parallel majors with the same name are not supported yet")
            seen[key].add(symbol)
        known = SCALARS | set(raw.get("types", {}))
        for fields in (raw["input"], raw["output"], *raw.get("types", {}).values()):
            for field_name in fields:
                portable_identifier(field_name)
            for value in fields.values():
                if TypeRef.parse(value).base not in known:
                    raise ValueError(f"{raw['urn']}: unknown local type {value}")
        for name, fields in raw.get("types", {}).items():
            portable_identifier(name)
            if name in types and types[name] != fields:
                raise ValueError(f"conflicting shared type: {name}")
            types[name] = fields
    generated = {name + kind for name in seen["type"] for kind in ("Input", "Output")}
    if generated & types.keys():
        raise ValueError("shared type collides with generated input/output type")


def load_cells(root: Path = ROOT) -> list[Cell]:
    cells = []
    parsed = [(p, yaml.safe_load(p.read_text(encoding="utf-8")))
              for p in sorted((root / "contracts" / "cells").glob("*.cell.yaml"))]
    validate_contract_set([raw for _, raw in parsed])
    for p, raw in parsed:
        cells.append(Cell(
            path=p, raw=raw, urn=raw["urn"], name=raw["name"], owner=raw["owner"],
            input=_fields(raw.get("input")), output=_fields(raw.get("output")),
            types={t: _fields(f) for t, f in (raw.get("types") or {}).items()},
            root=root,
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
