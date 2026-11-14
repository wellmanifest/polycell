"""MCP client errors must not terminate the server or dispatch another tool."""
import json
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

from gateway import mcp


@contextmanager
def gateway_reply(body=None, *, status=200, drop=False, incomplete=False):
    """Record completed requests, optionally losing the response afterwards."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            args = json.loads(self.rfile.read(int(self.headers["content-length"])))
            calls.append((self.path, args))
            if drop:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send_response(status)
            self.send_header("Content-Length", str(len(body) + (10 if incomplete else 0)))
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def tool_request():
    return {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "example", "arguments": {"value": 7}}}


class MCPTests(unittest.TestCase):
    def test_transport_failure_never_replays_locally(self):
        failures = [TimeoutError("response timed out"), ConnectionResetError("lost response"),
                    urllib.error.URLError("connection refused"), http.client.IncompleteRead(b"{")]
        for kind in ("cell", "process"):
            for failure in failures:
                with self.subTest(kind=kind, failure=type(failure).__name__), \
                     patch.dict(mcp.ROUTES, {"example": [(kind, "example")]}, clear=True), \
                     patch.object(mcp.urllib.request, "urlopen", side_effect=failure) as remote, \
                     patch.object(mcp.core, "invoke", return_value={"ok": True}) as cell, \
                     patch.object(mcp.core, "run_process", return_value={"ok": True}) as process:
                    response = mcp.handle(tool_request())
                    self.assertEqual(-32603, response["error"]["code"])
                    self.assertIn("may have completed", response["error"]["message"])
                    remote.assert_called_once()
                    cell.assert_not_called()
                    process.assert_not_called()

    def test_completed_http_call_with_lost_response_is_not_replayed(self):
        for kind in ("cell", "process"):
            with self.subTest(kind=kind), gateway_reply(drop=True) as (base, calls), \
                 patch.object(mcp, "GATEWAY", base), \
                 patch.dict(mcp.ROUTES, {"example": [(kind, "example")]}, clear=True), \
                 patch.object(mcp.core, "invoke", return_value={"ok": True}) as cell, \
                 patch.object(mcp.core, "run_process", return_value={"ok": True}) as process:
                response = mcp.handle(tool_request())
                self.assertEqual(-32603, response["error"]["code"])
                path = "/api/process/example" if kind == "process" else "/api/cells/example"
                self.assertEqual([(path, {"value": 7})], calls)
                cell.assert_not_called()
                process.assert_not_called()

    def test_invalid_http_response_never_replays_locally(self):
        for body, incomplete in ((b"null", False), (b"[]", False), (b"{", False), (b"{}", True)):
            with self.subTest(body=body, incomplete=incomplete), \
                 gateway_reply(body, incomplete=incomplete) as (base, calls), \
                 patch.object(mcp, "GATEWAY", base), \
                 patch.dict(mcp.ROUTES, {"example": [("cell", "example")]}, clear=True), \
                 patch.object(mcp.core, "invoke", return_value={"ok": True}) as cell:
                response = mcp.handle(tool_request())
                self.assertEqual(-32603, response["error"]["code"])
                self.assertEqual(1, len(calls))
                cell.assert_not_called()

    def test_explicit_local_mode_dispatches_once_without_http(self):
        for kind in ("cell", "process"):
            with self.subTest(kind=kind), \
                 patch.dict(mcp.ROUTES, {"example": [(kind, "example")]}, clear=True), \
                 patch.object(mcp, "via_gateway") as remote, \
                 patch.object(mcp.core, "invoke", return_value={"ok": True}) as cell, \
                 patch.object(mcp.core, "run_process", return_value={"ok": True}) as process:
                self.assertFalse(mcp.handle(tool_request(), local=True)["result"]["isError"])
                selected, other = (cell, process) if kind == "cell" else (process, cell)
                selected.assert_called_once_with("example", {"value": 7})
                other.assert_not_called()
                remote.assert_not_called()

    def test_http_success_and_business_error_are_returned_without_local_dispatch(self):
        for status, payload in ((200, {"ok": True, "output": {"value": 7}}),
                                (422, {"ok": False, "error": "invalid customer"})):
            with self.subTest(status=status), gateway_reply(json.dumps(payload).encode(), status=status) as (base, calls), \
                 patch.object(mcp, "GATEWAY", base), \
                 patch.dict(mcp.ROUTES, {"example": [("process", "example")]}, clear=True), \
                 patch.object(mcp.core, "run_process") as process:
                response = mcp.handle(tool_request())["result"]
                self.assertEqual(not payload["ok"], response["isError"])
                self.assertEqual(payload, json.loads(response["content"][0]["text"]))
                self.assertEqual(1, len(calls))
                process.assert_not_called()

    def test_stdio_survives_lost_gateway_response(self):
        with gateway_reply(drop=True) as (base, calls):
            name = next(name for name, routes in mcp.ROUTES.items() if len(routes) == 1)
            request = tool_request()
            request["params"]["name"] = name
            messages = [request, {"jsonrpc": "2.0", "id": 10, "method": "tools/list"}]
            result = subprocess.run([sys.executable, "-m", "gateway.mcp"],
                                    input="".join(json.dumps(msg) + "\n" for msg in messages), text=True,
                                    env={**os.environ, "WM_GATEWAY_URL": base}, capture_output=True,
                                    timeout=10, check=True)
            responses = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(-32603, responses[0]["error"]["code"])
            self.assertEqual(10, responses[1]["id"])
            self.assertIn("tools", responses[1]["result"])
            self.assertEqual(1, len(calls))

    def test_stdio_local_mode_uses_own_database_without_http(self):
        with tempfile.TemporaryDirectory() as directory, gateway_reply(drop=True) as (base, calls):
            database = os.path.join(directory, "local.sqlite")
            request = tool_request()
            request["params"] = {"name": "shipping_cost", "arguments": {}}
            result = subprocess.run([sys.executable, "-m", "gateway.mcp", "--local"],
                                    input=json.dumps(request) + "\n", text=True, capture_output=True,
                                    env={**os.environ, "WM_GATEWAY_URL": base, "WM_DB": "sqlite://" + database},
                                    timeout=10, check=True)
            reply = json.loads(result.stdout)
            self.assertTrue(reply["result"]["isError"])
            payload = json.loads(reply["result"]["content"][0]["text"])
            self.assertIn("input contract:", payload["error"])
            self.assertEqual([], calls)
            with sqlite3.connect(database) as connection:
                self.assertEqual(1, connection.execute("select count(*) from wm_invocations").fetchone()[0])

    def test_malformed_line_does_not_stop_stdio_server(self):
        request = {"jsonrpc": "2.0", "id": 7, "method": "tools/list"}
        result = subprocess.run([sys.executable, "-m", "gateway.mcp"],
                                input="{\n" + json.dumps(request) + "\n", text=True,
                                capture_output=True, timeout=10, check=True)
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(-32700, lines[0]["error"]["code"])
        self.assertEqual(7, lines[1]["id"])
        self.assertIn("tools", lines[1]["result"])

    def test_invalid_requests_do_not_dispatch(self):
        messages = [[], None, {"method": "tools/list", "id": 1},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": []},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "unknown"}},
                    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "x", "arguments": []}}]
        with patch.object(mcp, "via_gateway") as call:
            for message in messages:
                with self.subTest(message=message):
                    self.assertIn("error", mcp.handle(message))
            call.assert_not_called()

    def test_process_prefix_in_cell_name_dispatches_to_cell(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "process_foo"}}
        with patch.dict(mcp.ROUTES, {"process_foo": [("cell", "process.foo")]}, clear=True), \
             patch.object(mcp, "via_gateway", return_value={"ok": True}) as call:
            self.assertFalse(mcp.handle(message)["result"]["isError"])
            call.assert_called_once_with("cell", "process.foo", {})

    def test_ambiguous_name_fails_closed(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "process_foo"}}
        with patch.dict(mcp.ROUTES, {"process_foo": [("cell", "process.foo"), ("process", "foo")]}, clear=True), \
             patch.object(mcp, "via_gateway") as call:
            self.assertEqual(-32602, mcp.handle(message)["error"]["code"])
            call.assert_not_called()

    def test_notifications_have_no_response(self):
        self.assertIsNone(mcp.handle({"jsonrpc": "2.0", "method": "tools/list"}))


if __name__ == "__main__":
    unittest.main()
