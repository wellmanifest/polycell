"""Qualification must validate wire metadata before trusting correct outputs."""
from copy import deepcopy
import unittest
from unittest.mock import Mock

from jsonschema import Draft202012Validator

from tools.polycell.comparison import outputs_equal
from tools.polycell.package_worker import validate_reply


class QualificationEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.meta = {"urn": "urn:wm:cell:test:example:v1", "owner": "python", "contract": "expected"}
        self.case = {"name": "example:valid", "input": {"value": True}, "output": {"value": True}}
        self.reply = {"urn": self.meta["urn"], "lang": "python", "ok": True,
                      "output": self.case["output"], "error": "", "duration_ms": 0, "contract": "expected"}
        self.validator = Draft202012Validator({"type": "object", "required": ["value"],
                                              "properties": {"value": {}}})

    def reject_envelope(self, reply):
        compare = Mock(wraps=outputs_equal)
        with self.assertRaisesRegex(ValueError, "example:valid: invalid host response"):
            validate_reply(self.case, reply, self.meta, self.validator, compare)
        compare.assert_not_called()

    def test_success_flag_must_be_boolean(self):
        for value in (1, "true", "false", [True], {"value": True}):
            with self.subTest(value=value):
                self.reject_envelope({**self.reply, "ok": value})

    def test_reply_must_match_qualified_urn_and_language(self):
        for key, value in (("urn", "urn:wm:cell:other:example:v1"), ("lang", "rust"),
                           ("urn", 7), ("lang", None)):
            with self.subTest(key=key, value=value):
                self.reject_envelope({**self.reply, key: value})

    def test_complete_wire_envelope_is_required(self):
        for key in self.reply:
            with self.subTest(missing=key):
                reply = {field: value for field, value in self.reply.items() if field != key}
                self.reject_envelope(reply)

    def test_success_must_have_consistent_string_error_metadata(self):
        for error in ("operation failed", None, False, 7, {}):
            with self.subTest(error=error):
                self.reject_envelope({**self.reply, "error": error})

    def test_duration_must_be_finite_nonnegative_number(self):
        for value in (-1, True, "1", None, {}, float("nan"), float("inf"), -float("inf")):
            with self.subTest(numeric_value=value):
                self.reject_envelope({**self.reply, "duration_ms": value})

    def test_nonfinite_or_non_json_metadata_is_rejected(self):
        for value in ({"nested": float("nan")}, [float("inf")], object()):
            with self.subTest(value=value):
                self.reject_envelope({**self.reply, "extra": value})
        cyclic = deepcopy(self.reply)
        cyclic["extra"] = cyclic
        self.reject_envelope(cyclic)

    def test_valid_success_retains_contract_schema_and_behavior_checks(self):
        original = deepcopy(self.reply)
        validate_reply(self.case, self.reply, self.meta, self.validator, outputs_equal)
        self.assertEqual(original, self.reply)
        for change, message in (({"contract": "wrong"}, "host contract mismatch"),
                                ({"output": None}, "output contract"),
                                ({"output": {"value": 1}}, "behavior mismatch")):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                validate_reply(self.case, {**self.reply, **change}, self.meta, self.validator, outputs_equal)

    def test_valid_host_failure_keeps_actionable_diagnostic(self):
        reply = {**self.reply, "ok": False, "output": None, "error": "ValueError: unsupported country"}
        compare = Mock(wraps=outputs_equal)
        with self.assertRaisesRegex(ValueError, "example:valid: host error: ValueError: unsupported country"):
            validate_reply(self.case, reply, self.meta, self.validator, compare)
        compare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
