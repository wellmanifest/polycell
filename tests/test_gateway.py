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
    def test_finite_json_schema_rejects_nested_nonfinite_values(self):
        schema = {'type': 'object', 'properties': {'data': {}}, 'required': ['data']}
        for value in (float('nan'), float('inf'), -float('inf')):
            for data in (value, [value], {'nested': [value]}):
                with self.subTest(value=value, data=data):
                    self.assertTrue(core.validate({'data': data}, schema))

    def test_finite_json_schema_preserves_ordinary_values(self):
        for value in (None, False, True, 0, -1, 1.25, 1e-300, 'NaN', 'Infinity', 'Zażółć',
                      [None, False, 0, {'nested': 'text'}], {'values': [1, 2.5]}):
            with self.subTest(value=value):
                self.assertEqual([], core.validate({'data': value}, {'type': 'object', 'properties': {'data': {}}}))

    def test_finite_json_invocation_stops_before_host_and_database(self):
        schema = {'type': 'object', 'properties': {'data': {}}, 'required': ['data']}
        for value in (float('nan'), float('inf'), {'nested': [-float('inf')]}):
            for protocol in transport.TRANSPORTS:
                with self.subTest(value=value, protocol=protocol), patch.object(core, '_schema', return_value=schema), patch.object(
                        transport, 'call', return_value={'ok': True, 'output': {'data': None},
                            'contract': core.CELLS[core.BY_NAME['shipping.cost']]['contract']}) as dispatch, patch.object(core, 'db') as database:
                    result = core.invoke('shipping.cost', {'data': value}, protocol)
                    self.assertIs(result['ok'], False)
                    self.assertIn('input JSON', result['error'])
                    dispatch.assert_not_called()
                    database.assert_not_called()
                    json.dumps(result, allow_nan=False)

    def test_finite_json_valid_invocation_still_dispatches_and_persists(self):
        data = {'data': [None, False, 0, 'NaN', {'text': 'Zażółć'}]}
        response = {'ok': True, 'output': data, 'contract': core.CELLS[core.BY_NAME['shipping.cost']]['contract']}
        schema = {'type': 'object', 'properties': {'data': {}}, 'required': ['data']}
        with patch.object(core, '_schema', return_value=schema), patch.object(transport, 'call', return_value=response) as dispatch, patch.object(core, 'db') as database:
            result = core.invoke('shipping.cost', data)
        self.assertIs(result['ok'], True)
        dispatch.assert_called_once()
        database.return_value.insert.assert_called_once()

    def test_finite_json_rejects_nonserializable_and_circular_values_cleanly(self):
        circular = []
        circular.append(circular)
        for value in (object(), {1, 2}, circular):
            with self.subTest(kind=type(value).__name__):
                self.assertTrue(core.validate(value, {}))

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

    def test_finite_json_http_rejects_constants_and_overflow_before_routing(self):
        with patch.object(core, 'invoke', return_value={'ok': True}) as invoke, patch.object(
                core, 'run_process', return_value={'ok': True}) as process, patch.object(
                core, 'nl_match', return_value={'matched': False}) as nl, patch.object(core, 'db') as database:
            for numeric_literal in ('NaN', 'Infinity', '-Infinity', '1e400', '-1e400'):
                body = ('{"urn":"urn:wm:cell:shop:shipping.cost:v1","input":{"data":[' + numeric_literal + ']},"text":"hello"}').encode()
                for endpoint in ('/api/invoke', '/api/cells/shipping.cost', '/api/process/checkout', '/api/nl'):
                    with self.subTest(numeric_literal=numeric_literal, endpoint=endpoint):
                        status, result = self.request(endpoint, body)
                        self.assertEqual(400, status, result)
                        self.assertIs(result['ok'], False)
                        self.assertIn('finite', result['error'])
            invoke.assert_not_called()
            process.assert_not_called()
            nl.assert_not_called()
            database.assert_not_called()
        self.assertEqual(200, self.request('/api/registry')[0])

    def test_finite_json_http_preserves_quoted_tokens_null_and_finite_numbers(self):
        data = {'data': ['NaN', 'Infinity', '-Infinity', None, False, 0, 1.25, 1e-300, 'Zażółć']}
        body = json.dumps({'urn': 'urn:wm:cell:shop:shipping.cost:v1', 'input': data}, allow_nan=False).encode()
        with patch.object(core, 'invoke', return_value={'ok': True}) as invoke:
            self.assertEqual(200, self.request('/api/invoke', body)[0])
        self.assertEqual(data, invoke.call_args.args[1])

    def test_missing_urn_returns_structured_error(self):
        self.assertEqual(400, self.request("/api/invoke", b"{}")[0])

    def test_unknown_process_returns_structured_error(self):
        self.assertEqual(400, self.request("/api/process/missing", b"{}")[0])
        self.assertEqual(400, self.request("/api/process/missing/plan")[0])

    def test_invalid_limit_returns_structured_error(self):
        self.assertEqual(400, self.request("/api/invocations?limit=invalid")[0])


if __name__ == "__main__":
    unittest.main()
