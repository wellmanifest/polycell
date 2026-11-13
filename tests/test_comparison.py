"""Behavior oracles preserve JSON kinds and exact integer values."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gateway import core
from tools.polycell.package_worker import validate_reply


class OutputComparisonTests(unittest.TestCase):
    def assertEquivalent(self, expected, left, right):
        self.assertIs(expected, core._eq(left, right))
        self.assertIs(expected, core._eq(right, left))

    def test_booleans_are_not_numbers_even_in_nested_json(self):
        for boolean, number in ((True, 1), (True, 1.0), (False, 0), (False, 0.0)):
            with self.subTest(boolean=boolean, number=number):
                self.assertEquivalent(False, boolean, number)
                self.assertEquivalent(False, {'data': [boolean]}, {'data': [number]})
        self.assertEquivalent(True, {'data': [True, False]}, {'data': [True, False]})

    def test_large_mixed_numbers_cannot_be_rounded_into_equality(self):
        for integer, number in ((2**53 + 1, float(2**53)), (-(2**53 + 1), -float(2**53)),
                                (10**400, 1e308)):
            with self.subTest(integer=integer):
                self.assertEquivalent(False, integer, number)
        self.assertEquivalent(True, 2**53, float(2**53))

    def test_integer_comparison_is_exact(self):
        self.assertEquivalent(True, 2**63 - 1, 2**63 - 1)
        self.assertEquivalent(False, 2**63 - 1, 2**63 - 2)
        self.assertEquivalent(False, 10**400, 10**400 + 1)

    def test_finite_numeric_tolerance_is_preserved(self):
        for left, right in ((1, 1.0), (1, 1 + 5e-10), (1.5, 1.5 + 5e-10), (0, -0.0)):
            with self.subTest(left=left, right=right):
                self.assertEquivalent(True, left, right)
        self.assertEquivalent(False, 0, 1e-9)
        self.assertEquivalent(False, 1.5, 1.5 + 2e-9)

    def test_nonfinite_values_never_match(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(value=value):
                self.assertEquivalent(False, value, value)
                self.assertEquivalent(False, {'data': [value]}, {'data': [value]})
                self.assertEquivalent(False, value, 10**400)

    def test_json_shapes_null_and_order(self):
        self.assertEquivalent(True, {'a': None, 'b': [1, 'x']}, {'b': [1.0, 'x'], 'a': None})
        for left, right in (({}, {'a': None}), (None, {}), ([1, 2], [2, 1]),
                            ([1], [1, 2]), ('1', 1), ([], {}), ('', None)):
            with self.subTest(left=left, right=right):
                self.assertEquivalent(False, left, right)

    def test_non_json_python_objects_do_not_match(self):
        for value in ((1,), {1}, object()):
            with self.subTest(value=value):
                self.assertEquivalent(False, value, value)

    def test_gateway_parity_reports_json_behavior_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'tests/generated').mkdir(parents=True)
            (root / 'tests/generated/cases.json').write_text(json.dumps([
                {'name': 'json-value', 'owner': 'python', 'urn': 'urn:wm:cell:test:json.echo:v1',
                 'input': {'data': True}, 'output': {'data': True}}]))
            with patch.object(core, 'ROOT', root), patch.object(core, 'invoke', return_value={
                    'ok': True, 'output': {'data': 1}}):
                self.assertFalse(core.parity()['all_ok'])

    def test_qualification_rejects_json_behavior_change(self):
        validator = Draft202012Validator({'type': 'object', 'properties': {'data': {}}, 'required': ['data']})
        for expected, actual in (({'nested': [True]}, {'nested': [1]}),
                                 (2**53 + 1, float(2**53))):
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, 'behavior mismatch'):
                validate_reply({'name': 'json-value', 'output': {'data': expected}},
                               {'ok': True, 'contract': 'hash', 'output': {'data': actual}},
                               {'contract': 'hash'}, validator, core._eq)

    def test_qualification_accepts_small_numeric_error(self):
        validator = Draft202012Validator({'type': 'object', 'properties': {'data': {}}})
        validate_reply({'name': 'numeric', 'output': {'data': 1.5}},
                       {'ok': True, 'contract': 'hash', 'output': {'data': 1.5 + 5e-10}},
                       {'contract': 'hash'}, validator, core._eq)
