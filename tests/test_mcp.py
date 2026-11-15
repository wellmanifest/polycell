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

    def test_stdio_unicode_ids_keep_utf8_wire_and_server_alive(self):
        cases = (("strict", ["\ud800", "\udfff", "Zażółć 🌍", 31]),
                 ("surrogateescape", ["\udcff", "Zażółć 🌍", 32]))
        for errors, ids in cases:
            with self.subTest(stdout_errors=errors):
                messages = [{"jsonrpc": "2.0", "id": mid, "method": "tools/list"} for mid in ids]
                wire = "".join(json.dumps(msg) + "\n" for msg in messages).encode("utf-8")
                result = subprocess.run([sys.executable, "-m", "gateway.mcp"],
                                        input=wire, capture_output=True, timeout=10, check=True,
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8:" + errors})
                responses = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
                self.assertEqual(ids, [reply["id"] for reply in responses])
                for reply in responses:
                    self.assertIn("tools", reply["result"])

    def test_stdio_unicode_gateway_reply_is_not_replayed_and_server_recovers(self):
        payload = {"ok": True, "output": {"text": "\ud800", "unicode": "Zażółć 🌍"}}
        with gateway_reply(json.dumps(payload).encode("utf-8")) as (base, calls):
            request = tool_request()
            request["params"]["name"] = "shipping_cost"
            messages = [request, {"jsonrpc": "2.0", "id": 12, "method": "tools/list"}]
            result = subprocess.run([sys.executable, "-m", "gateway.mcp"],
                                    input="".join(json.dumps(msg) + "\n" for msg in messages).encode("utf-8"),
                                    capture_output=True, timeout=10, check=True,
                                    env={**os.environ, "WM_GATEWAY_URL": base, "PYTHONIOENCODING": "utf-8:strict"})
            responses = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
            self.assertEqual([9, 12], [reply["id"] for reply in responses])
            self.assertFalse(responses[0]["result"]["isError"])
            self.assertEqual(payload, json.loads(responses[0]["result"]["content"][0]["text"]))
            self.assertIn("tools", responses[1]["result"])
            self.assertEqual([("/api/cells/shipping.cost", {"value": 7})], calls)

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

    def test_invalid_request_ids_do_not_dispatch(self):
        invalid = (True, False, None, [], {}, [1], {"x": 1}, 1.5, -0.5)
        for kind in ("cell", "process"):
            for local in (False, True):
                with patch.dict(mcp.ROUTES, {"example": [(kind, "example")]}, clear=True), \
                     patch.object(mcp, "via_gateway", return_value={"ok": True}) as remote, \
                     patch.object(mcp.core, "invoke", return_value={"ok": True}) as cell, \
                     patch.object(mcp.core, "run_process", return_value={"ok": True}) as process:
                    for mid in invalid:
                        with self.subTest(kind=kind, local=local, mid=mid):
                            message = tool_request()
                            message["id"] = mid
                            self.assertEqual({"jsonrpc": "2.0", "id": None,
                                              "error": {"code": -32600, "message": "Invalid Request"}},
                                             mcp.handle(message, local=local))
                    remote.assert_not_called()
                    cell.assert_not_called()
                    process.assert_not_called()

    def test_stdio_request_ids_are_checked_before_dispatch_and_server_recovers(self):
        invalid = (True, False, None, [], {}, [1], {"x": 1}, 1.5, -0.5)
        valid = (0, -7, 2**64, "", "Zażółć 🌍", 1.0, 2.0)
        messages = []
        for ids, key in ((invalid, "rejected"), (valid, "accepted")):
            for index, mid in enumerate(ids):
                messages.append({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                                 "params": {"name": "shipping_cost", "arguments": {key: index}}})
        messages.extend([{"jsonrpc": "2.0", "method": "tools/call",
                          "params": {"name": "shipping_cost", "arguments": {"notification": True}}},
                         {"jsonrpc": "2.0", "id": "after-id-checks", "method": "tools/list"}])
        wire = "".join(json.dumps(message) + "\n" for message in messages)
        wire = wire.replace('"id": 1.0,', '"id": 1e0,')
        with gateway_reply(b'{"ok":true}') as (base, calls):
            result = subprocess.run([sys.executable, "-m", "gateway.mcp"],
                                    input=wire.encode("utf-8"), capture_output=True, timeout=10, check=True,
                                    env={**os.environ, "WM_GATEWAY_URL": base, "PYTHONIOENCODING": "utf-8:strict"})
            responses = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
            self.assertEqual(len(invalid) + len(valid) + 1, len(responses))
            for response in responses[:len(invalid)]:
                self.assertEqual({"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32600, "message": "Invalid Request"}}, response)
            accepted = responses[len(invalid):-1]
            self.assertEqual(list(valid), [response["id"] for response in accepted])
            for response in accepted:
                self.assertFalse(response["result"]["isError"])
            self.assertEqual("after-id-checks", responses[-1]["id"])
            self.assertIn("tools", responses[-1]["result"])
            self.assertEqual([("/api/cells/shipping.cost", {"accepted": i})
                              for i in range(len(valid))], calls)

    def test_stdio_rejects_nonfinite_numbers_before_dispatch_and_recovers(self):
        literals = ("NaN", "Infinity", "-Infinity", "1e400", "-1e400")
        messages = []
        for literal in literals:
            messages.append('{"jsonrpc":"2.0","id":' + literal + ',"method":"tools/list"}')
            request = tool_request()
            request["params"] = {"name": "shipping_cost", "arguments": {"value": ["NUMBER"]}}
            messages.append(json.dumps(request).replace('"NUMBER"', literal))
        for index, literal in enumerate(literals[:3], start=20):
            messages.append(json.dumps({"jsonrpc": "2.0", "id": index, "method": "tools/call",
                                        "params": {"name": "shipping_cost", "arguments": {"value": [literal]}}}))
        messages.append(json.dumps({"jsonrpc": "2.0", "id": 30, "method": "tools/list"}))
        with gateway_reply(b'{"ok":true}') as (base, calls):
            result = subprocess.run([sys.executable, "-m", "gateway.mcp"],
                                    input="\n".join(messages) + "\n", text=True, capture_output=True,
                                    env={**os.environ, "WM_GATEWAY_URL": base}, timeout=10, check=True)
            responses = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(messages), len(responses))
            for response in responses[:10]:
                self.assertEqual({"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32700, "message": "Parse error"}}, response)
            for index, response in enumerate(responses[10:13], start=20):
                self.assertEqual(index, response["id"])
                self.assertFalse(response["result"]["isError"])
            self.assertEqual(30, responses[-1]["id"])
            self.assertIn("tools", responses[-1]["result"])
            json.dumps(responses, allow_nan=False)
            self.assertEqual([("/api/cells/shipping.cost", {"value": [literal]})
                              for literal in literals[:3]], calls)

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
