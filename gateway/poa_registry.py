"""Describe Polycell cells, POA processes, and gateway queries as a POA registry."""
from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from . import core

SCHEMA = "polycell.poa-registry/v1"
SYSTEM = "polycell"
REGISTRY_VERSION = "1.0.0"
READ_ONLY = ("pure",)


def _unique_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _cell_operation(urn: str, meta: Mapping[str, Any]) -> dict[str, Any]:
    parts = urn.split(":")
    fallback_name = parts[-2] if len(parts) >= 2 else urn
    name = str(meta.get("name") or fallback_name)
    tail = parts[-1] if parts else ""
    ver = tail if tail.startswith("v") else "v1"
    read_only = not bool(meta.get("persist"))
    effects = list(READ_ONLY) if read_only else ["db:write"]
    nl = meta.get("nl") if isinstance(meta.get("nl"), Mapping) else {}
    triggers = _unique_text([*(nl.get("pl") or []), *(nl.get("en") or []), name])
    uri = f"proc://wellmanifest/polycell/cell/{name}/{ver}"
    return {
        "id": f"poa:{uri}",
        "uri": uri,
        "system": SYSTEM,
        "kind": "query" if read_only else "proc",
        "desc": str(meta.get("summary") or f"Polycell {meta.get('owner', 'cell')} cell {name}"),
        "triggers": triggers,
        "effects": effects,
        "aliases": [f"proc://wellmanifest/polycell/cell/{name}"],
        "parameters": {"input": "object", "transport": "string?"},
        "canonical": True,
        "available": True,
        "urn": urn,
        "command": f"python3 -m gateway.cli call {name}",
        "authority": "none" if read_only else "polycell",
        "sensitivity": "public" if read_only else "standard",
    }


def _process_operation(pname: str, pmeta: Mapping[str, Any]) -> dict[str, Any]:
    process_ref = str(pmeta.get("process_ref") or f"poa://polycell.local/process/{pname}/v1")
    tail = process_ref.rsplit("/", 1)[-1]
    ver = tail if tail.startswith("v") else "v1"
    step_effects: list[str] = []
    for step in pmeta.get("steps") or ():
        if isinstance(step, Mapping):
            step_effects.extend(str(e) for e in (step.get("effects") or ()))
    effects = _unique_text(step_effects) or list(READ_ONLY)
    read_only = set(effects) <= {"pure", "read_data"}
    title = str(pmeta.get("title") or f"Polycell POA process {pname}")
    uri = f"proc://wellmanifest/polycell/process/{pname}/{ver}"
    return {
        "id": f"poa:{uri}",
        "uri": uri,
        "system": SYSTEM,
        "kind": "query" if read_only else "proc",
        "desc": title,
        "triggers": _unique_text([pname, title]),
        "effects": effects,
        "aliases": _unique_text([process_ref, f"proc://wellmanifest/polycell/process/{pname}"]),
        "parameters": {"input": "object", "transport": "string?"},
        "canonical": True,
        "available": True,
        "urn": None,
        "command": f"python3 -m gateway.cli process {pname}",
        "authority": "none" if read_only else "polycell",
        "sensitivity": "public" if read_only else "standard",
    }


def _gateway_queries() -> list[dict[str, Any]]:
    return [
        {
            "id": "poa:proc://wellmanifest/polycell/parity/v1",
            "uri": "proc://wellmanifest/polycell/parity/v1",
            "system": SYSTEM,
            "kind": "query",
            "desc": "Run read-only Polycell HTTP/gRPC/stdio protocol parity verification",
            "triggers": ["polycell parity", "check cell parity", "sprawdz parytet"],
            "effects": list(READ_ONLY),
            "aliases": ["proc://wellmanifest/polycell/parity"],
            "parameters": {},
            "canonical": True,
            "available": True,
            "urn": None,
            "command": "python3 -m gateway.cli parity",
            "authority": "none",
            "sensitivity": "public",
        },
        {
            "id": "poa:proc://wellmanifest/polycell/poa-registry/v1",
            "uri": "proc://wellmanifest/polycell/poa-registry/v1",
            "system": SYSTEM,
            "kind": "query",
            "desc": "Export Polycell cells, POA processes, and gateway queries in /v1/poa/registry format",
            "triggers": ["polycell poa registry", "export polycell poa"],
            "effects": list(READ_ONLY),
            "aliases": ["proc://wellmanifest/polycell/poa-registry"],
            "parameters": {},
            "canonical": True,
            "available": True,
            "urn": None,
            "command": "python3 -m gateway.cli poa-registry",
            "authority": "none",
            "sensitivity": "public",
        },
    ]


def poa_registry(
    cells: Mapping[str, Any] | None = None,
    processes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the Polycell POA registry payload; metadata only, zero authority."""
    cell_map = core.CELLS if cells is None else cells
    process_map = core.PROCESSES if processes is None else processes
    operations: list[dict[str, Any]] = [
        _cell_operation(urn, meta) for urn, meta in sorted(cell_map.items())
    ]
    operations.extend(
        _process_operation(pname, pmeta) for pname, pmeta in sorted(process_map.items())
    )
    operations.extend(_gateway_queries())
    return {
        "schema": SCHEMA,
        "version": REGISTRY_VERSION,
        "total": len(operations),
        "systems": [SYSTEM],
        "operations": operations,
    }


def main(argv: list[str] | None = None) -> int:
    """Print the Polycell POA registry JSON payload to stdout."""
    del argv
    print(json.dumps(poa_registry(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0
