"""Regression tests at the gateway boundary; no live hosts or database required."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from gateway import core, transport
from gateway.app import H


class ValidationTests(unittest.TestCase):
    def test_required_null_is_rejected_before_dispatch(self):
        with patch.object(transport, "call") as dispatch:
            result = core.invoke("customer.validate", {"name": None, "email": "a@b.pl", "country": "PL"}, persist=False)
        self.assertFalse(result["ok"])
        self.assertIn("$.name: expected string", result["error"])
        dispatch.assert_not_called()

    def test_nested_null_is_rejected(self):
        result = core.invoke("pricing.quote", {"items": [{"sku": "A", "qty": None, "unit_price": 10}], "currency": "PLN"}, persist=False)
        self.assertFalse(result["ok"])
        self.assertIn("$.items[0].qty", result["error"])

    def test_optional_field_can_be_omitted(self):
        self.assertEqual([], core.validate({"items": [], "currency": "PLN"}, core._schema("pricing.quote", "input")))

    def test_booleans_are_not_numbers(self):
        self.assertTrue(core.validate(True, {"type": "integer"}))
        self.assertTrue(core.validate(False, {"type": "number"}))

    def test_unknown_fields_are_rejected(self):
        self.assertTrue(core.validate({"weight_kg": 2, "country": "PL", "extra": 1}, core._schema("shipping.cost", "input")))

    def test_missing_or_stale_host_hash_is_rejected(self):
        for contract in (None, "outdated"):
            with self.subTest(contract=contract), patch.object(transport, "call", return_value={"ok": True, "output": {"result": 9.99}, "contract": contract}):
                result = core.invoke("shipping.cost", {"weight_kg": 2, "country": "PL"}, persist=False)
            self.assertFalse(result["ok"])
            self.assertIn("contract mismatch", result["error"])

    def test_invalid_output_is_rejected(self):
        with patch.object(transport, "call", return_value={"ok": True, "output": {"result": None}}):
            result = core.invoke("shipping.cost", {"weight_kg": 2, "country": "PL"}, persist=False)
        self.assertFalse(result["ok"])
        self.assertIn("output contract", result["error"])

    def test_unknown_transport_returns_failure(self):
        result = transport.call("python", "invalid", "urn:wm:probe", {})
        self.assertFalse(result["ok"])
        self.assertIn("unsupported transport", result["error"])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=body, headers={"content-type": "application/json"})
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_bad_json_returns_structured_error_and_server_survives(self):
        for body in (b"{", b"[]", b"null", b'"text"'):
            with self.subTest(body=body):
                status, result = self.request("/api/invoke", body)
                self.assertEqual(400, status)
                self.assertFalse(result["ok"])
        self.assertEqual(200, self.request("/api/registry")[0])

    def test_missing_urn_returns_structured_error(self):
        self.assertEqual(400, self.request("/api/invoke", b"{}")[0])

    def test_unknown_process_returns_structured_error(self):
        self.assertEqual(400, self.request("/api/process/missing", b"{}")[0])
        self.assertEqual(400, self.request("/api/process/missing/plan")[0])

    def test_invalid_limit_returns_structured_error(self):
        self.assertEqual(400, self.request("/api/invocations?limit=invalid")[0])


if __name__ == "__main__":
    unittest.main()
