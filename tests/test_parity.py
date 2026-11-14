"""Parity must validate its entire execution matrix before contacting hosts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gateway import core


class ParityPreflightTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.root / 'tests/generated/cases.json'
        self.path.parent.mkdir(parents=True)
        self.cells = {f'urn:wm:cell:test:probe.{owner}:v1': {'owner': owner, 'name': 'probe.' + owner}
                      for owner in ('python', 'ts', 'rust')}
        self.cases = [{'urn': urn, 'owner': meta['owner'], 'name': meta['name'] + ':ok',
                       'input': {'value': 1}, 'output': {'value': 1}} for urn, meta in self.cells.items()]
        self.enterContext(patch.object(core, 'ROOT', self.root))
        self.enterContext(patch.object(core, 'CELLS', self.cells))
        self.enterContext(patch.object(core, '_schema', return_value={
            'type': 'object', 'properties': {'value': {}}, 'required': ['value'], 'additionalProperties': False}))
        self.dispatch = self.enterContext(patch.object(core, 'invoke', return_value={
            'ok': True, 'output': {'value': 1}, 'rtt_ms': 0.25}))

    def write(self, cases):
        self.path.write_text(json.dumps(cases))

    def assert_failed(self, cases, transports=('http', 'grpc', 'stdio')):
        self.write(cases)
        self.dispatch.reset_mock()
        result = core.parity(transports)
        self.assertIs(result['all_ok'], False, result)
        self.assertEqual([], result['rows'])
        self.assertTrue(result['errors'])
        self.dispatch.assert_not_called()
        json.dumps(result, allow_nan=False)
        return result

    def test_empty_catalog_does_not_pass(self):
        self.assert_failed([])

    def test_every_registered_cell_requires_coverage(self):
        result = self.assert_failed(self.cases[:-1])
        self.assertIn(self.cases[-1]['urn'], ' '.join(result['errors']))

    def test_invalid_or_empty_transport_selection_stops_before_dispatch(self):
        for selection in ((), [], None, 'http', ('invalid',), ('http', 'http'), ('http', ['grpc'])):
            with self.subTest(selection=selection):
                self.assert_failed(self.cases, selection)

    def test_case_identity_and_names_are_validated_before_any_call(self):
        for changes in ({'urn': 'unknown'}, {'urn': []}, {'owner': 'wrong'},
                        {'name': ''}, {'name': self.cases[0]['name']}):
            with self.subTest(changes=changes):
                cases = deepcopy(self.cases)
                cases[-1].update(changes)
                self.assert_failed(cases)

    def test_missing_case_fields_are_a_failed_report(self):
        for field in ('urn', 'owner', 'name', 'input', 'output'):
            with self.subTest(field=field):
                cases = deepcopy(self.cases)
                del cases[-1][field]
                self.assert_failed(cases)

    def test_invalid_shapes_and_schemas_are_not_executed(self):
        for catalog in (None, {}, 'cases', [None], [1]):
            with self.subTest(kind=type(catalog).__name__):
                self.assert_failed(catalog)
        for kind, value in (('input', {}), ('input', []), ('output', {'other': 1}),
                            ('output', {'value': float('nan')})):
            with self.subTest(kind=kind, value=value):
                cases = deepcopy(self.cases)
                cases[-1][kind] = value
                self.assert_failed(cases)

    def test_unreadable_or_malformed_catalog_is_a_failed_report(self):
        for text in (None, '{'):
            with self.subTest(text=text):
                if text is None:
                    self.path.unlink(missing_ok=True)
                else:
                    self.path.write_text(text)
                result = core.parity()
                self.assertIs(result['all_ok'], False)
                self.assertTrue(result['errors'])
                self.dispatch.assert_not_called()

    def test_valid_full_matrix_keeps_rows_and_timings(self):
        self.write(self.cases)
        result = core.parity()
        self.assertIs(result['all_ok'], True, result)
        self.assertEqual([], result['errors'])
        self.assertEqual(3, len(result['rows']))
        self.assertEqual(9, self.dispatch.call_count)
        for row in result['rows']:
            for protocol in ('http', 'grpc', 'stdio'):
                self.assertEqual('ok', row[protocol])
                self.assertEqual(0.25, row[protocol + '_rtt_ms'])

    def test_missing_or_invalid_generated_schema_stops_before_dispatch(self):
        for schema in (None, [], 'schema'):
            with self.subTest(schema=schema), patch.object(core, '_schema', return_value=schema):
                self.assert_failed(self.cases)
        for failure in (FileNotFoundError('missing schema'), ValueError('invalid schema JSON')):
            with self.subTest(failure=type(failure).__name__), patch.object(core, '_schema', side_effect=failure):
                self.assert_failed(self.cases)

    def test_valid_explicit_subset_only_executes_requested_transport(self):
        self.write(self.cases)
        result = core.parity(['http'])
        self.assertIs(result['all_ok'], True, result)
        self.assertEqual([], result['errors'])
        self.assertEqual(3, self.dispatch.call_count)
        self.assertTrue(all(call.args[2] == 'http' for call in self.dispatch.call_args_list))
        self.assertTrue(all('grpc' not in row and 'stdio' not in row for row in result['rows']))

    def test_golden_only_case_names_remain_valid_coverage(self):
        cases = deepcopy(self.cases)
        for case in cases:
            case['name'] = case['name'].split(':')[0] + ':golden0'
        self.write(cases)
        result = core.parity()
        self.assertIs(result['all_ok'], True, result)
        self.assertEqual(9, self.dispatch.call_count)

    def test_empty_registry_does_not_produce_vacuous_success(self):
        with patch.object(core, 'CELLS', {}):
            self.assert_failed([])


if __name__ == '__main__':
    unittest.main()
