"""Serwer MCP (JSON-RPC 2.0 po stdio) - narzędzia generowane z gen/mcp-tools.json.
Agent AI (Claude Code, Cursor itd.) widzi te same komórki co REST/gRPC: parytet interfejsów.

  {"mcpServers": {"polycell": {"command": "python", "args": ["-m", "gateway.mcp"], "cwd": "<repo>"}}}
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from . import core

TOOLS = json.loads((core.ROOT / "gen/mcp-tools.json").read_text())["tools"]
TOOLS += [{"name": f"process_{n}", "description": p["title"], "inputSchema": {"type": "object"}}
          for n, p in core.PROCESSES.items()]


TOOL2CELL = {m["name"].replace(".", "_"): m["name"] for m in core.CELLS.values()}
GATEWAY = os.environ.get("WM_GATEWAY_URL", "http://127.0.0.1:8080")


def via_gateway(name: str, args: dict) -> dict | None:
    """Preferuj działający gateway: jeden zapis do DB (PGlite = jedno połączenie), wspólne logi i trace."""
    path = f"/api/process/{name.removeprefix('process_')}" if name.startswith("process_") else f"/api/cells/{TOOL2CELL.get(name, name)}"
    req = urllib.request.Request(GATEWAY + path, data=json.dumps(args).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())
    except OSError:
        return None


def handle(msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        res = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
               "serverInfo": {"name": "polycell", "version": "0.1.0"}}
    elif method == "tools/list":
        res = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = params["name"], params.get("arguments") or {}
        r = via_gateway(name, args)
        if r is None:  # gateway nie działa -> ten sam rdzeń lokalnie
            r = core.run_process(name.removeprefix("process_"), args) if name.startswith("process_") \
                else core.invoke(TOOL2CELL.get(name, name), args)
        res = {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False)}], "isError": not r.get("ok")}
    elif mid is None:
        return None  # notyfikacja
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def main():
    for line in sys.stdin:
        if line.strip():
            out = handle(json.loads(line))
            if out:
                sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    main()
