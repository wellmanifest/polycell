"""MCP client errors must not terminate the server or dispatch another tool."""
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from gateway import mcp


class MCPTests(unittest.TestCase):
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
