"""Rdzeń gatewaya: walidacja kontraktu, routing URN -> host, zapis do DB, procesy POA, NL, parity."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

from tools.polycell.comparison import outputs_equal as _eq
from tools.polycell.guards import guard_matches, parse_guard

from . import transport
from .db import DB

ROOT = transport.ROOT
INDEX = json.loads((ROOT / "gen/cells.index.json").read_text())
CELLS: dict = INDEX["cells"]
PROCESSES: dict = INDEX["processes"]
REGISTRY = json.loads((ROOT / "gen/registry.json").read_text())
BY_NAME = {m["name"]: u for u, m in CELLS.items()}
DEFAULT_TRANSPORT = os.environ.get("WM_TRANSPORT", "grpc")
_db: DB | None = None


def db() -> DB:
    global _db
    if _db is None:
        _db = DB()
    return _db


# ------------------------------------------------------------- mini JSON Schema (bez zależności)
def _schema(name: str, kind: str) -> dict:
    return json.loads((ROOT / "gen/jsonschema" / f"{name}.{kind}.json").read_text())


def _json_error(value) -> str | None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return "expected finite JSON value"
    return None


def validate(value, schema: dict, defs: dict | None = None, path: str = "$") -> list[str]:
    if problem := _json_error(value):
        return [f"{path}: {problem}"]
    return _validate(value, schema, defs, path)


def _validate(value, schema: dict, defs: dict | None = None, path: str = "$") -> list[str]:
    """Apply schema rules after the complete value passed JSON preflight once."""
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return _validate(value, defs[schema["$ref"].split("/")[-1]], defs, path)
    t = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "boolean": bool}
    if t in checks and not isinstance(value, checks[t]):
        return [f"{path}: expected {t}"]
    if t == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return [f"{path}: expected integer"]
    if t == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return [f"{path}: expected number"]
    errs: list[str] = []
    if t in ("integer", "number"):
        if isinstance(value, float) and not math.isfinite(value):
            return [f"{path}: expected finite {t}"]
        for bound, outside in (("minimum", lambda limit: value < limit),
                               ("maximum", lambda limit: value > limit)):
            if bound in schema and outside(schema[bound]):
                errs.append(f"{path}: outside {bound} {schema[bound]}")
    if t == "object":
        props = schema.get("properties", {})
        errs += [f"{path}.{k}: required" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            errs += [f"{path}.{k}: unknown field" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                errs += _validate(v, props[k], defs, f"{path}.{k}")
    if t == "array":
        for i, v in enumerate(value):
            errs += _validate(v, schema.get("items", {}), defs, f"{path}[{i}]")
    return errs


# ------------------------------------------------------------- wywołanie komórki
def invoke(urn_or_name: str, data: dict, transport_name: str | None = None, trace_id: str | None = None,
           persist: bool = True) -> dict:
    urn = BY_NAME.get(urn_or_name, urn_or_name)
    trace_id = trace_id or uuid.uuid4().hex[:16]
    tr = transport_name or DEFAULT_TRANSPORT
    if urn not in CELLS:
        return {"ok": False, "urn": urn, "error": "unknown urn", "trace_id": trace_id}
    meta = CELLS[urn]
    if problem := _json_error(data):
        return {"urn": urn, "ok": False, "output": None, "error": "input JSON: " + problem,
                "lang": meta["owner"], "transport": tr, "trace_id": trace_id}
    errs = _validate(data, _schema(meta["name"], "input"))
    if errs:
        r = {"urn": urn, "ok": False, "output": None, "error": "input contract: " + "; ".join(errs), "lang": meta["owner"],
             "transport": tr}
    else:
        r = transport.call(meta["owner"], tr, urn, data, trace_id)
        if r.get("ok"):
            oerrs = validate(r["output"], _schema(meta["name"], "output"))
            if oerrs:  # komórka złamała kontrakt -> fail-closed (luka wykryta zanim trafi do klienta)
                r.update(ok=False, error="output contract: " + "; ".join(oerrs))
            elif r.get("contract") != meta["contract"]:
                r.update(ok=False, error=f"contract mismatch host={r.get('contract')} registry={meta['contract']}")
    r["trace_id"] = trace_id
    if persist:
        _persist(urn, meta, data, r)
    return r


def _persist(urn: str, meta: dict, data: dict, r: dict) -> None:
    try:
        d = db()
        d.insert("wm_invocations", {"trace_id": r["trace_id"], "urn": urn, "transport": r.get("transport", "?"),
                                    "lang": r.get("lang"), "ok": bool(r.get("ok")), "input": data, "output": r.get("output"),
                                    "error": r.get("error") or None, "duration_ms": r.get("duration_ms"),
                                    "contract": meta["contract"]}, {"input", "output"})
        if meta.get("persist") and r.get("ok"):
            row, jcols = {"trace_id": r["trace_id"]}, set()
            for prefix, fields, src in (("in", meta["input"], data), ("out", meta["output"], r["output"])):
                for k, t in fields.items():
                    col = f"{prefix}_{k}"
                    row[col] = src.get(k)
                    if t["is_list"] or t["base"] not in ("string", "int32", "int64", "double", "bool"):
                        jcols.add(col)
            d.insert(meta["persist"], row, jcols)
    except Exception as e:  # noqa: BLE001 - zapis nie może zatrzymać odpowiedzi; trafia do logów
        log(event="persist_error", urn=urn, error=str(e))


# ------------------------------------------------------------- POA: proces = kompozycja URN
_MISSING = object()


def _get(ctx: dict, expr):
    if not (isinstance(expr, str) and expr.startswith("$.")):
        return expr
    cur = ctx
    for part in expr[2:].split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _resolve(mapping, ctx):
    if isinstance(mapping, dict):
        resolved = {}
        for key, value in mapping.items():
            if isinstance(value, str) and value.startswith('$.'):
                value = _get(ctx, value)
                if value is _MISSING:
                    continue
            else:
                value = _resolve(value, ctx)
            resolved[key] = value
        return resolved
    if isinstance(mapping, list):
        return [_resolve(value, ctx) for value in mapping]
    value = _get(ctx, mapping)
    if value is _MISSING:
        raise ValueError(f'unresolved process reference: {mapping}')
    return value


def plan(name: str, tr: str) -> dict:
    return _plan(deepcopy(PROCESSES[name]), tr)


def _plan(p: dict, tr: str) -> dict:
    if tr not in transport.TRANSPORTS:
        raise ValueError(f"unsupported process transport: {tr}")
    seen = set()
    steps = []
    for s in p["steps"]:
        step_id = s.get("id")
        if not isinstance(step_id, str) or not step_id or step_id in seen:
            raise ValueError(f"invalid or duplicate process step id: {step_id}")
        dependencies = s.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(d, str) for d in dependencies):
            raise ValueError(f"invalid dependencies at process step {step_id}")
        missing = [d for d in dependencies if d not in seen]
        if missing or s["capability_ref"] not in CELLS:
            raise ValueError(f"invalid process step {s['id']}: deps={missing} urn={s['capability_ref']}")
        if "guard" in s:
            try:
                parse_guard(s["guard"])
            except ValueError as error:
                raise ValueError(f"invalid process guard at {s['id']}: {error}") from error
        seen.add(s["id"])
        owner = CELLS[s["capability_ref"]]["owner"]
        steps.append({"id": s["id"], "capability_ref": s["capability_ref"], "contract": CELLS[s["capability_ref"]]["contract"],
                      "binding": f"{tr}://host-{owner}", "input": s.get("input", {}), "depends_on": dependencies,
                      **{key: s[key] for key in ("guard", "kind", "effects") if key in s}})
    # The compact plan includes every execution mapping. Detach its nested data
    # so neither the registry nor an invocation can rewrite the hashed content.
    body = deepcopy({"schema": "poa.plan/v1", "process_ref": p["process_ref"], "steps": steps,
                     "input": p.get("input", {}), "output": p.get("output", {})})
    body["plan_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return body


def run_process(name: str, data: dict, tr: str | None = None) -> dict:
    tr = tr or DEFAULT_TRANSPORT
    if problem := _json_error(data):
        raise ValueError("input JSON: " + problem)
    p = deepcopy(PROCESSES[name])
    pl = _plan(p, tr)
    trace_id = uuid.uuid4().hex[:16]
    ctx = {**data, "steps": {}}
    receipt = {"schema": "poa.receipt/v1", "process_ref": p["process_ref"], "plan_hash": pl["plan_hash"],
               "trace_id": trace_id, "steps": []}
    ok, error = True, ""
    for s in p["steps"]:
        try:
            arguments = _resolve(s.get("input", {}), ctx)
        except ValueError as mapping_error:
            meta = CELLS[s['capability_ref']]
            r = {'ok': False, 'error': f'input mapping: {mapping_error}', 'lang': meta['owner'],
                 'transport': tr, 'contract': meta['contract']}
        else:
            r = invoke(s["capability_ref"], arguments, tr, trace_id)
        receipt["steps"].append({k: r.get(k) for k in ("ok", "lang", "transport", "duration_ms", "contract", "error")} | {"id": s["id"]})
        if not r.get("ok"):
            ok, error = False, f"step {s['id']}: {r.get('error')}"
            break
        ctx["steps"][s["id"]] = r["output"]
        if "guard" in s and not guard_matches(s["guard"], ctx):
            ok, error = False, f"guard failed at {s['id']}: {s['guard']}"
            break
    out = None
    if ok:
        try:
            out = _resolve(p.get("output", {}), ctx)
        except ValueError as mapping_error:
            ok, error = False, f'output mapping: {mapping_error}'
    if not ok:
        receipt['error'] = error
    res = {"ok": ok, "error": error, "output": out, "receipt": receipt, "plan": pl}
    try:
        db().insert("wm_process_runs", {"trace_id": trace_id, "process_ref": p["process_ref"], "ok": ok,
                                        "input": data, "output": out, "receipt": receipt}, {"input", "output", "receipt"})
    except Exception as e:  # noqa: BLE001
        log(event="persist_error", process=name, error=str(e))
    return res


# ------------------------------------------------------------- NL -> API (fast path + opcjonalny LLM)
def _tok(s: str) -> set[str]:
    return set(re.findall(r"\w+", s.lower()))


def nl_match(text: str) -> dict:
    words = _tok(text)
    best = {"score": 0.0}
    for ep in REGISTRY["endpoints"]:
        for intent in ep.get("nlIntents", []):
            for ph in intent["phrases"]:
                pt = _tok(ph)
                score = len(words & pt) / max(len(pt), 1)
                if score > best["score"]:
                    best = {"score": round(score, 2), "endpoint": ep["id"], "path": ep.get("rest", {}).get("path"),
                            "phrase": ph, "lang": intent["lang"]}
    best["matched"] = best["score"] >= 0.6
    if not best["matched"] and os.environ.get("LLM_BASE_URL"):
        best["llm"] = _llm_compile(text)
    return best


def _llm_compile(text: str) -> dict:
    """Fallback LLM (dowolne API zgodne z OpenAI). Model może wybrać TYLKO endpoint z rejestru -
    odpowiedź jest walidowana; nic poza listą nie zostanie wykonane (fail-closed, jak w nl-dsl-llm)."""
    import urllib.request
    ids = [e["id"] for e in REGISTRY["endpoints"] if e["protocol"] == "rest"]
    prompt = (f"Choose one endpoint id from {ids} for the user request and return JSON "
              f'{{"endpoint": "<id>", "input": {{...}}}}. Request: {text}')
    req = urllib.request.Request(os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions",
                                 data=json.dumps({"model": os.environ.get("LLM_MODEL", "local"),
                                                  "messages": [{"role": "user", "content": prompt}],
                                                  "response_format": {"type": "json_object"}}).encode(),
                                 headers={"content-type": "application/json",
                                          "authorization": f"Bearer {os.environ.get('LLM_API_KEY', '')}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(json.loads(r.read())["choices"][0]["message"]["content"])
        return out if out.get("endpoint") in ids else {"error": "llm chose unknown endpoint"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# ------------------------------------------------------------- parity: te same przypadki na każdym protokole
def parity(transports=transport.TRANSPORTS) -> dict:
    errors = []
    if not isinstance(transports, (tuple, list)) or not transports:
        return {"all_ok": False, "rows": [], "errors": ["select a nonempty list of transports"]}
    transports = tuple(transports)
    seen_transports = set()
    for selected in transports:
        if not isinstance(selected, str) or selected not in transport.TRANSPORTS:
            errors.append(f"unsupported parity transport: {selected}")
        elif selected in seen_transports:
            errors.append(f"duplicate parity transport: {selected}")
        else:
            seen_transports.add(selected)
    if errors:
        return {"all_ok": False, "rows": [], "errors": errors}
    try:
        cases = json.loads((ROOT / "tests/generated/cases.json").read_text())
    except (OSError, ValueError) as error:
        return {"all_ok": False, "rows": [], "errors": [f"cannot read parity cases: {error}"]}
    if not CELLS:
        errors.append("no registered cells to test")
    if not isinstance(cases, list) or not cases:
        errors.append("parity cases must be a nonempty list")
    if errors:
        return {"all_ok": False, "rows": [], "errors": errors}
    covered, names, schemas = set(), set(), {}
    for number, case in enumerate(cases):
        label = f"case[{number}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: expected object")
            continue
        missing = {"urn", "owner", "name", "input", "output"} - case.keys()
        if missing:
            errors.append(f"{label}: missing fields: {', '.join(sorted(missing))}")
            continue
        name, urn = case["name"], case["urn"]
        if not isinstance(name, str) or not name.strip() or name in names:
            errors.append(f"{label}: invalid or duplicate name")
            continue
        names.add(name)
        if not isinstance(urn, str) or urn not in CELLS:
            errors.append(f"{name}: unknown cell URN")
            continue
        meta = CELLS[urn]
        if case["owner"] != meta["owner"]:
            errors.append(f"{name}: owner does not match registry")
            continue
        prior_errors = len(errors)
        for kind in ("input", "output"):
            try:
                if (urn, kind) not in schemas:
                    schemas[urn, kind] = _schema(meta["name"], kind)
                if not isinstance(schemas[urn, kind], dict):
                    raise ValueError("generated schema must be an object")
                errors.extend(f"{name} {kind}: {message}"
                              for message in validate(case[kind], schemas[urn, kind]))
            except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
                errors.append(f"{name} {kind}: cannot validate generated schema: {error}")
        if len(errors) == prior_errors:
            covered.add(urn)
    for urn in sorted(set(CELLS) - covered):
        errors.append(f"no valid parity case for {urn}")
    if errors:
        return {"all_ok": False, "rows": [], "errors": errors}
    rows = []
    for c in cases:
        row = {"case": c["name"], "lang": c["owner"]}
        for tr in transports:
            r = invoke(c["urn"], c["input"], tr, persist=False)
            row[tr] = "ok" if r.get("ok") and _eq(r["output"], c["output"]) else f"FAIL {r.get('error') or r.get('output')}"
            row[f"{tr}_rtt_ms"] = r.get("rtt_ms")
        rows.append(row)
    return {"all_ok": all(row[t] == "ok" for row in rows for t in transports), "rows": rows, "errors": []}


# ------------------------------------------------------------- logi (ring buffer + docker socket)
LOGS: list[dict] = []


def log(**kw) -> None:
    rec = {"ts": time.time(), "svc": "gateway", **kw}
    LOGS.append(rec)
    del LOGS[:-500]
    print(json.dumps(rec, ensure_ascii=False), file=sys.stderr, flush=True)  # stdout zostaje czyste (MCP/stdio)


def docker_logs(tail: int = 100) -> dict:
    """Logi wszystkich kontenerów projektu przez /var/run/docker.sock (tylko odczyt).
    W trybie natywnym (make dev) czyta .run/logs/*.log."""
    sock = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")
    out: dict[str, list[str]] = {}
    if Path(sock).exists():
        import http.client
        import socket

        class Unix(http.client.HTTPConnection):
            def connect(self):
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(sock)

        def get(path):
            c = Unix("localhost")
            c.request("GET", path)
            return c.getresponse().read()

        project = os.environ.get("COMPOSE_PROJECT_NAME", "polycell")
        flt = json.dumps({"label": [f"com.docker.compose.project={project}"]})
        import urllib.parse
        for ctr in json.loads(get("/containers/json?filters=" + urllib.parse.quote(flt))):
            raw = get(f"/containers/{ctr['Id']}/logs?stdout=1&stderr=1&tail={tail}")
            lines, i = [], 0
            while i + 8 <= len(raw):  # multipleksowany strumień docker: 8-bajtowy nagłówek
                n = int.from_bytes(raw[i + 4:i + 8], "big")
                lines += raw[i + 8:i + 8 + n].decode(errors="replace").splitlines()
                i += 8 + n
            out[ctr["Names"][0].lstrip("/")] = lines
    for f in sorted((ROOT / ".run/logs").glob("*.log")):
        out[f.stem] = f.read_text(errors="replace").splitlines()[-tail:]
    out["gateway(memory)"] = [json.dumps(r, ensure_ascii=False) for r in LOGS[-tail:]]
    return out
