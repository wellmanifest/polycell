"""Process guards must reject ambiguous contracts and stop downstream calls."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from gateway import core
from standard.conformance import run as conformance


class ProcessGuardTests(unittest.TestCase):
    def setUp(self):
        urn = "urn:wm:cell:test:guard.probe:v1"
        self.process = {
            "schema": "poa.process/v1",
            "process_ref": "poa://test.local/process/guard/v1",
            "steps": [
                {"id": "first", "capability_ref": urn, "input": {},
                 "guard": "$.steps.first.value == true"},
                {"id": "next", "capability_ref": urn, "depends_on": ["first"], "input": {}},
            ],
            "output": {"result": "$.steps.next"},
        }
        self.enterContext(patch.object(core, "PROCESSES", {"probe": self.process}))
        self.enterContext(patch.object(core, "CELLS", {urn: {"owner": "python", "contract": "test-hash"}}))
        self.dispatch = self.enterContext(patch.object(core, "invoke"))
        self.database = Mock()
        self.enterContext(patch.object(core, "db", return_value=self.database))

    def execute(self, output):
        self.dispatch.reset_mock()
        self.dispatch.return_value = {"ok": True, "output": output}
        return core.run_process("probe", {})

    def test_invalid_guards_rejected_before_dispatch(self):
        invalid = [None, False, 0, {}, [], "", " ", "true",
                   "$.steps.first.value != true", "$.steps.first.value = true",
                   "$.steps..first.value == true", "$.steps.first.value. == true",
                   "$.steps.first.value == True", "$.steps.first.value == true trailing",
                   "$.steps.first.value == NaN", "$.steps.first.value == Infinity",
                   "$.steps.first.value == -Infinity", "$.steps.first.value == 1e400",
                   '$.steps.first.value == {"nested": [NaN]}',
                   '$.steps.first.value == {"a": 1, "a": 2}']
        for guard in invalid:
            with self.subTest(guard=guard):
                self.process["steps"][0]["guard"] = guard
                with self.assertRaisesRegex(ValueError, "guard.*first"):
                    self.execute({"value": True})
                self.dispatch.assert_not_called()
                self.database.insert.assert_not_called()

    def test_invalid_later_guard_rejected_before_first_step(self):
        self.process["steps"][1]["guard"] = "$.steps.next.value == invalid-json"
        with self.assertRaisesRegex(ValueError, "guard.*next"):
            self.execute({"value": True})
        self.dispatch.assert_not_called()

    def test_false_guard_stops_downstream_and_persists_failure(self):
        result = self.execute({"value": False})
        self.assertFalse(result["ok"])
        self.assertIsNone(result["output"])
        self.assertIn("guard failed at first", result["error"])
        self.assertEqual(1, self.dispatch.call_count)
        self.assertEqual(["first"], [step["id"] for step in result["receipt"]["steps"]])
        self.assertFalse(self.database.insert.call_args.args[1]["ok"])

    def test_boolean_and_number_are_distinct_even_when_nested(self):
        for actual, expected in [(1, True), (True, 1), (0, False), (False, 0),
                                 ({"a": [1]}, {"a": [True]}), ([False], [0])]:
            with self.subTest(actual=actual, expected=expected):
                self.process["steps"][0]["guard"] = "$.steps.first.value == " + json.dumps(expected)
                self.assertFalse(self.execute({"value": actual})["ok"])
                self.assertEqual(1, self.dispatch.call_count)

    def test_missing_field_never_matches_null(self):
        self.process["steps"][0]["guard"] = "$.steps.first.value == null"
        for output in ({}, {"other": None}, None, []):
            with self.subTest(output=output):
                self.assertFalse(self.execute(output)["ok"])
                self.assertEqual(1, self.dispatch.call_count)

    def test_explicit_null_matches_null(self):
        self.process["steps"][0]["guard"] = "$.steps.first.value == null"
        self.assertTrue(self.execute({"value": None})["ok"])
        self.assertEqual(2, self.dispatch.call_count)

    def test_valid_json_values_match(self):
        for actual, expected in [(True, True), (False, False), (1, 1.0), (1.0, 1),
                                 ('a "quoted" value', 'a "quoted" value'),
                                 ({"a": [1, None, False], "b": {}}, {"b": {}, "a": [1.0, None, False]})]:
            with self.subTest(actual=actual):
                self.process["steps"][0]["guard"] = "  $.steps.first.value == " + json.dumps(expected) + "  "
                self.assertTrue(self.execute({"value": actual})["ok"])
                self.assertEqual(2, self.dispatch.call_count)

    def test_different_json_values_stop_execution(self):
        for actual, expected in [([1], [1, 2]), ({"a": 1}, {"b": 1}), ([], {}), ("1", 1)]:
            with self.subTest(actual=actual):
                self.process["steps"][0]["guard"] = "$.steps.first.value == " + json.dumps(expected)
                self.assertFalse(self.execute({"value": actual})["ok"])
                self.assertEqual(1, self.dispatch.call_count)

    def test_absent_guard_allows_execution(self):
        del self.process["steps"][0]["guard"]
        self.assertTrue(self.execute({"value": False})["ok"])
        self.assertEqual(2, self.dispatch.call_count)


class GuardConformanceTests(unittest.TestCase):
    def test_invalid_guard_is_a_contract_finding(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in ("contracts", "cells", "gen"):
                shutil.copytree(root / name, fixture / name)
            path = fixture / "contracts/processes/checkout.process.yaml"
            process = yaml.safe_load(path.read_text())
            for guard in (None, False, "", "$.steps.validate.valid != true", "$.steps.validate.valid == NaN"):
                with self.subTest(guard=guard):
                    process["steps"][0]["guard"] = guard
                    path.write_text(yaml.safe_dump(process))
                    findings = conformance(fixture)
                    self.assertTrue(any(f["code"] == "PC006" and "guard" in f["message"] for f in findings), findings)
            process["steps"][0]["guard"] = "$.steps.validate.valid == true"
            path.write_text(yaml.safe_dump(process))
            self.assertEqual([], [f for f in conformance(fixture) if f["severity"] == "error"])


if __name__ == "__main__":
    unittest.main()
