"""Polycell gateway: REST + UI + NL + procesy POA + diagnostyka (logi, parity, invocations).

  python -m gateway.app                 # :8080
  python -m gateway.mcp                 # ten sam katalog komórek jako serwer MCP (stdio)
  python -m gateway.cli call pricing.quote '{"items":[],"currency":"PLN"}'
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import core, transport

UI = core.ROOT / "gateway" / "ui" / "index.html"


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("content-length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _q(self):
        u = urlparse(self.path)
        return u.path, {k: v[0] for k, v in parse_qs(u.query).items()}

    def do_GET(self):  # noqa: N802
        try:
            return self._get()
        except (ValueError, KeyError, TypeError) as e:
            return self._send(400, {"ok": False, "error": str(e)})

    def _get(self):
        path, q = self._q()
        if path in ("/", "/index.html"):
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        if path == "/health":
            return self._send(200, {"ok": True, "transport": core.DEFAULT_TRANSPORT, "db": core.db().kind})
        if path == "/api/registry":
            return self._send(200, core.REGISTRY)
        if path == "/api/cells":
            return self._send(200, core.INDEX)
        if path == "/api/hosts":
            return self._send(200, hosts())
        if path == "/api/invocations":
            lim = int(q.get("limit", 50))
            return self._send(200, core.db().query(
                "select id, trace_id, urn, transport, lang, ok, duration_ms, error, created_at from wm_invocations order by id desc limit ?", (lim,)))
        if path.startswith("/api/table/"):
            tbl = path.split("/")[3]
            allowed = {"wm_invocations", "wm_process_runs"} | {m["persist"] for m in core.CELLS.values() if m.get("persist")}
            if tbl not in allowed:
                return self._send(404, {"error": "unknown table"})
            return self._send(200, core.db().query(f"select * from {tbl} order by id desc limit ?", (int(q.get("limit", 20)),)))
        if path == "/api/export":  # realne wywołania jako przypadki golden (strangler fig)
            return self._send(200, core.db().query(
                "select input, output from wm_invocations where urn = ? and ok = ? order by id", (q["urn"], True)))
        if path == "/api/logs":
            return self._send(200, core.docker_logs(int(q.get("tail", 100))))
        if path == "/api/parity":
            trs = tuple(q.get("transports", ",".join(transport.TRANSPORTS)).split(","))
            return self._send(200, core.parity(trs))
        if path.startswith("/api/process/") and path.endswith("/plan"):
            return self._send(200, core.plan(path.split("/")[3], q.get("transport", core.DEFAULT_TRANSPORT)))
        self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        try:
            return self._post()
        except (ValueError, KeyError, TypeError) as e:
            return self._send(400, {"ok": False, "error": str(e)})

    def _post(self):
        path, q = self._q()
        data = self._body()
        if not isinstance(data, dict):
            return self._send(400, {"ok": False, "error": "expected JSON object"})
        tr = q.get("transport") or self.headers.get("x-wm-transport")
        if path.startswith("/api/cells/"):
            r = core.invoke(path.split("/")[3], data, tr)
            return self._send(200 if r.get("ok") else 422, r)
        if path == "/api/invoke":
            r = core.invoke(data["urn"], data.get("input", {}), data.get("transport") or tr)
            return self._send(200 if r.get("ok") else 422, r)
        if path.startswith("/api/process/"):
            r = core.run_process(path.split("/")[3], data, tr)
            return self._send(200 if r["ok"] else 422, r)
        if path == "/api/nl":
            return self._send(200, core.nl_match(data.get("text", "")))
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        core.log(event="http", line=fmt % args)


def hosts() -> dict:
    out = {}
    for lang in transport.DEFAULTS:
        out[lang] = {}
        for tr in ("http", "grpc"):
            probe = next((u for u, m in core.CELLS.items() if m["owner"] == lang), None)
            r = transport.call(lang, tr, "urn:wm:probe", {}, "probe")
            # host żyje, jeśli odpowiada (nawet błędem "not hosted here")
            out[lang][tr] = "up" if "transport" in r and not str(r.get("error", "")).startswith("transport") else "down"
            out[lang]["cell"] = probe
    return out


def main():
    port = int(os.environ.get("PORT", 8080))
    core.log(event="listening", port=port, transport=core.DEFAULT_TRANSPORT, db=core.db().kind)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()
