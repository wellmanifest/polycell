"""MCP JSON-RPC server over stdio for cells and processes.

By default, calls use WM_GATEWAY_URL (http://127.0.0.1:8080). A failed or lost
HTTP response never triggers a local retry: the remote call may have completed.
Use ``python -m gateway.mcp --local`` to select direct execution before any call.
Local mode needs its own configured hosts and database connection; do not share
a single-connection PGlite database with a running gateway.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.error
import urllib.request

from . import core

TOOLS = json.loads((core.ROOT / "gen/mcp-tools.json").read_text())["tools"]
TOOLS += [{"name": f"process_{n}", "description": p["title"], "inputSchema": {"type": "object"}}
          for n, p in core.PROCESSES.items()]

# Keep all candidates: normalization or a process prefix may collide.
ROUTES: dict[str, list[tuple[str, str]]] = {}
for meta in core.CELLS.values():
    ROUTES.setdefault(meta["name"].replace(".", "_"), []).append(("cell", meta["name"]))
for name in core.PROCESSES:
    ROUTES.setdefault(f"process_{name}", []).append(("process", name))
GATEWAY = os.environ.get("WM_GATEWAY_URL", "http://127.0.0.1:8080")


def via_gateway(kind: str, name: str, args: dict) -> dict:
    path = f"/api/process/{name}" if kind == "process" else f"/api/cells/{name}"
    req = urllib.request.Request(GATEWAY + path, data=json.dumps(args).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        with error:
            return json.loads(error.read())


def error_response(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg, *, local: bool = False) -> dict | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return error_response(None, -32600, "Invalid Request")
    mid, method = msg.get("id"), msg["method"]
    if "id" not in msg:
        return None
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return error_response(mid, -32602, "Invalid params")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "polycell", "version": "0.1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(args, dict):
            return error_response(mid, -32602, "Invalid tool name or arguments")
        routes = ROUTES.get(name, [])
        if len(routes) != 1:
            return error_response(mid, -32602, "Unknown or ambiguous tool")
        kind, target = routes[0]
        try:
            if local:
                response = core.run_process(target, args) if kind == "process" else core.invoke(target, args)
            else:
                response = via_gateway(kind, target, args)
            if not isinstance(response, dict):
                raise ValueError("invalid gateway response")
        except (ValueError, KeyError, TypeError, OSError, http.client.HTTPException, RecursionError):
            message = ("Tool invocation failed" if local else
                       "Gateway response unavailable or invalid; execution may have completed. The call was not retried.")
            return error_response(mid, -32603, message)
        result = {"content": [{"type": "text", "text": json.dumps(response, ensure_ascii=False)}],
                  "isError": not response.get("ok")}
    else:
        return error_response(mid, -32601, f"unknown method {method}")
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="execute directly using configured hosts and database; skip HTTP gateway")
    args = parser.parse_args()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except (ValueError, RecursionError):
            out = error_response(None, -32700, "Parse error")
        else:
            out = handle(message, local=args.local)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
