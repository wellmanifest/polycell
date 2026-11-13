"""Cell host Python: ładuje komórki z cells/python/*.py i wystawia je przez
HTTP/JSON, gRPC (polycell.v1.CellHost) oraz stdio JSON-lines. Host jest generyczny -
nie zna żadnej logiki biznesowej, więc nigdy nie wymaga refaktoryzacji.

  python hosts/python/host.py            # HTTP :8101 + gRPC :9101
  python hosts/python/host.py --stdio    # JSON-lines na stdin/stdout
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from concurrent import futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("POLYCELL_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "gen" / "python"))
LANG = "python"
INDEX = json.loads((ROOT / "gen" / "cells.index.json").read_text())["cells"]
_cache: dict[str, tuple[float, object]] = {}


def log(**kw) -> None:
    print(json.dumps({"ts": time.time(), "svc": "host-python", **kw}, ensure_ascii=False), file=sys.stderr, flush=True)


def load(urn: str):
    meta = INDEX[urn]
    path = ROOT / "cells" / "python" / f"{meta['name'].replace('.', '_')}.py"
    mtime = path.stat().st_mtime
    hit = _cache.get(urn)
    if hit and hit[0] == mtime:
        return hit[1]
    spec = importlib.util.spec_from_file_location(f"cell_{meta['name'].replace('.', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # hot-reload: podmiana pliku komórki działa bez restartu
    _cache[urn] = (mtime, mod)
    log(event="cell_loaded", urn=urn, path=str(path.relative_to(ROOT)))
    return mod


def mine() -> list[str]:
    return [u for u, m in INDEX.items() if m["owner"] == LANG]


def invoke(urn: str, data: dict, trace_id: str = "") -> dict:
    t0 = time.perf_counter()
    res = {"urn": urn, "ok": False, "output": None, "error": "", "lang": LANG,
           "contract": INDEX.get(urn, {}).get("contract", "")}
    try:
        if urn not in mine():
            raise KeyError(f"urn not hosted here: {urn}")
        res["output"] = load(urn).run(data)
        res["ok"] = True
    except Exception as e:  # noqa: BLE001 - błąd komórki to dane, nie crash hosta
        res["error"] = f"{type(e).__name__}: {e}"
    res["duration_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    log(event="invoke", urn=urn, ok=res["ok"], ms=res["duration_ms"], trace_id=trace_id, error=res["error"] or None)
    return res


class Http(BaseHTTPRequestHandler):
    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            return self._send(200, {"ok": True, "lang": LANG})
        if self.path == "/v1/cells":
            return self._send(200, {"lang": LANG, "cells": [{"urn": u, "contract": INDEX[u]["contract"]} for u in mine()]})
        self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/v1/invoke":
            return self._send(404, {"error": "not found"})
        req = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        self._send(200, invoke(req["urn"], req.get("input") or {}, req.get("trace_id", "")))

    def log_message(self, *a):  # cisza; logujemy strukturalnie
        pass


def serve_grpc(port: int):
    try:
        import grpc
        from polycell.v1 import cellhost_pb2 as pb, cellhost_pb2_grpc as rpc
    except ImportError:
        log(event="grpc_disabled", reason="grpcio not installed")
        return None

    class Svc(rpc.CellHostServicer):
        def Invoke(self, request, context):  # noqa: N802
            r = invoke(request.urn, json.loads(request.json_input or "{}"), request.trace_id)
            return pb.InvokeResponse(urn=r["urn"], ok=r["ok"], json_output=json.dumps(r["output"], ensure_ascii=False),
                                     error=r["error"], lang=LANG, duration_ms=r["duration_ms"], contract=r["contract"])

        def List(self, request, context):  # noqa: N802
            return pb.ListResponse(lang=LANG, cells=[pb.CellInfo(urn=u, contract=INDEX[u]["contract"]) for u in mine()])

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    rpc.add_CellHostServicer_to_server(Svc(), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    return server


def serve_stdio() -> None:
    for line in sys.stdin:
        if line.strip():
            req = json.loads(line)
            print(json.dumps(invoke(req["urn"], req.get("input") or {}, req.get("trace_id", "")), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        serve_stdio()
        sys.exit(0)
    http_port = int(os.environ.get("HTTP_PORT", 8101))
    grpc_port = int(os.environ.get("GRPC_PORT", 9101))
    g = serve_grpc(grpc_port)
    log(event="listening", http=http_port, grpc=grpc_port if g else None, cells=mine())
    ThreadingHTTPServer(("0.0.0.0", http_port), Http).serve_forever()
