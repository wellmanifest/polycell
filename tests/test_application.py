"""Portable checks for the contracts actually installed in this application."""
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from standard.conformance import run

ROOT = Path(__file__).resolve().parents[1]


class ApplicationTests(unittest.TestCase):
    def test_conformance(self):
        self.assertEqual([], [finding for finding in run(ROOT) if finding['severity'] == 'error'])

    def test_cases_cover_registered_cells(self):
        cells = json.loads((ROOT / 'gen/cells.index.json').read_text())['cells']
        cases = json.loads((ROOT / 'tests/generated/cases.json').read_text())
        self.assertEqual(set(cells), {case['urn'] for case in cases})
        self.assertEqual(len(cases), len({case['name'] for case in cases}))
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(cells[case['urn']]['owner'], case['owner'])

    def test_schemas_and_behavior_fixtures(self):
        cells = json.loads((ROOT / 'gen/cells.index.json').read_text())['cells']
        cases = json.loads((ROOT / 'tests/generated/cases.json').read_text())
        validators = {}
        for urn, cell in cells.items():
            for kind in ('input', 'output'):
                schema = json.loads((ROOT / f"gen/jsonschema/{cell['name']}.{kind}.json").read_text())
                Draft202012Validator.check_schema(schema)
                validators[urn, kind] = Draft202012Validator(schema)
        for case in cases:
            with self.subTest(case=case['name']):
                for kind in ('input', 'output'):
                    validators[case['urn'], kind].validate(case[kind])


if __name__ == '__main__':
    unittest.main()
