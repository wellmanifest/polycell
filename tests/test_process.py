"""Process guards must reject ambiguous contracts and stop downstream calls."""
import json
import hashlib
from copy import deepcopy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from jsonschema import Draft202012Validator

from gateway import core
from standard.conformance import run as conformance


class ProcessGuardTests(unittest.TestCase):
    def test_finite_json_input_is_rejected_before_plan_dispatch_or_persistence(self):
        for data in ({'unused': float('nan')}, {'unused': [float('inf')]}, {'unused': {'x': -float('inf')}}):
            with self.subTest(data=data), patch.object(core, '_plan') as planner:
                with self.assertRaisesRegex(ValueError, 'input JSON'):
                    core.run_process('probe', data)
                planner.assert_not_called()
                self.dispatch.assert_not_called()
                self.database.insert.assert_not_called()

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
        self.assertEqual(result['error'], result['receipt']['error'])
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

    def test_hash_changes_with_every_execution_mapping(self):
        baseline = core.plan('probe', 'http')['plan_hash']
        changes = [
            lambda p: p.update(input={'flag': 'bool'}),
            lambda p: p.update(output={'result': '$.steps.first'}),
            lambda p: p['steps'][0].update(input={'flag': '$.flag'}),
            lambda p: p['steps'][0].update(guard='$.steps.first.value == false'),
            lambda p: p['steps'][1].update(depends_on=[]),
            lambda p: p['steps'][1].update(kind='command', effects=['local_write']),
        ]
        for change in changes:
            changed = deepcopy(self.process)
            change(changed)
            with self.subTest(process=changed), patch.object(core, 'PROCESSES', {'probe': changed}):
                self.assertNotEqual(baseline, core.plan('probe', 'http')['plan_hash'])

    def test_plan_hash_is_recomputable_and_snapshot_obeys_contract(self):
        plan = core.plan('probe', 'http')
        schema = json.loads((Path(__file__).resolve().parents[1] / 'standard/polycell-plan.schema.v1.json').read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(plan)
        self.assertEqual(self.process['steps'][0]['input'], plan['steps'][0]['input'])
        self.assertEqual(self.process['output'], plan['output'])
        digest = plan.pop('plan_hash')
        self.assertEqual(digest, hashlib.sha256(json.dumps(plan, sort_keys=True, allow_nan=False).encode()).hexdigest())
        legacy = {key: plan[key] for key in ('schema', 'process_ref', 'steps')}
        legacy['steps'] = [{key: step[key] for key in ('id', 'capability_ref', 'contract', 'binding')}
                           for step in plan['steps']]
        legacy['plan_hash'] = hashlib.sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest()
        Draft202012Validator(schema).validate(legacy)

    def test_documentation_and_dictionary_order_do_not_change_hash(self):
        original = core.plan('probe', 'grpc')['plan_hash']
        changed = dict(reversed(list(self.process.items())))
        changed.update(title='New description', examples=[{'note': 'documentation'}])
        with patch.object(core, 'PROCESSES', {'probe': changed}):
            self.assertEqual(original, core.plan('probe', 'grpc')['plan_hash'])

    def test_execution_uses_the_definition_that_was_planned(self):
        planned = core.plan('probe', 'http')['plan_hash']
        def dispatch(*args):
            self.process['steps'][1]['guard'] = '$.steps.next.value == false'
            return {'ok': True, 'output': {'value': True}}
        self.dispatch.side_effect = dispatch
        result = core.run_process('probe', {}, 'http')
        self.assertTrue(result['ok'])
        self.assertEqual(planned, result['receipt']['plan_hash'])
        self.assertNotEqual(planned, core.plan('probe', 'http')['plan_hash'])

    def test_plan_does_not_alias_mutable_process_data(self):
        plan = core.plan('probe', 'http')
        self.process['steps'][0]['input']['new'] = {'nested': [1]}
        self.process['output']['extra'] = '$.steps.first.value'
        self.assertEqual({}, plan['steps'][0]['input'])
        self.assertNotIn('extra', plan['output'])
        digest = plan.pop('plan_hash')
        self.assertEqual(digest, hashlib.sha256(json.dumps(plan, sort_keys=True, allow_nan=False).encode()).hexdigest())

    def test_duplicate_or_invalid_step_ids_rejected_before_dispatch(self):
        for step_id in ('first', '', None, []):
            with self.subTest(step_id=step_id):
                self.process['steps'][1]['id'] = step_id
                with self.assertRaises(ValueError):
                    self.execute({'value': True})
                self.dispatch.assert_not_called()

    def test_invalid_dependencies_and_transport_rejected_before_dispatch(self):
        for dependencies in ('first', [None], ['missing']):
            with self.subTest(dependencies=dependencies):
                self.process['steps'][1]['depends_on'] = dependencies
                with self.assertRaises(ValueError):
                    self.execute({'value': True})
                self.dispatch.assert_not_called()
        self.process['steps'][1]['depends_on'] = ['first']
        with self.assertRaises(ValueError):
            core.run_process('probe', {}, 'unsupported')
        self.dispatch.assert_not_called()

    def test_nonfinite_plan_values_fail_before_dispatch(self):
        self.process['steps'][0]['input'] = {'value': float('nan')}
        with self.assertRaises(ValueError):
            self.execute({'value': True})
        self.dispatch.assert_not_called()


class GuardConformanceTests(unittest.TestCase):
    def test_duplicate_step_is_a_contract_finding(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in ('contracts', 'cells', 'gen'):
                shutil.copytree(root / name, fixture / name)
            path = fixture / 'contracts/processes/checkout.process.yaml'
            process = yaml.safe_load(path.read_text())
            process['steps'][-1]['id'] = process['steps'][0]['id']
            path.write_text(yaml.safe_dump(process))
            findings = conformance(fixture)
            self.assertTrue(any(f['code'] == 'PC006' and 'duplicate' in f['message'] for f in findings), findings)

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


class ProcessMappingTests(unittest.TestCase):
    def setUp(self):
        self.urn = 'urn:wm:cell:test:mapping.echo:v1'
        self.process = {'schema': 'poa.process/v1', 'process_ref': 'poa://test/process/mapping/v1',
                        'steps': [{'id': 'echo', 'capability_ref': self.urn, 'input': {'data': '$.data'}}],
                        'output': {'data': '$.steps.echo.data'}}
        self.enterContext(patch.object(core, 'PROCESSES', {'mapping': self.process}))
        self.enterContext(patch.object(core, 'CELLS', {self.urn: {'owner': 'python', 'contract': 'mapping-hash'}}))
        def echo(urn, data, protocol, trace_id):
            if 'data' not in data:
                return {'ok': False, 'error': 'input contract: data required'}
            return {'ok': True, 'output': {'data': data['data']}, 'contract': 'mapping-hash'}
        self.dispatch = self.enterContext(patch.object(core, 'invoke', side_effect=echo))
        self.database = Mock()
        self.enterContext(patch.object(core, 'db', return_value=self.database))

    def test_literal_null_survives_input_and_output_maps(self):
        self.process['steps'][0]['input'] = {'data': None}
        self.process['output']['literal'] = None
        result = core.run_process('mapping', {})
        self.assertTrue(result['ok'], result)
        self.assertEqual({'data': None}, self.dispatch.call_args.args[1])
        self.assertEqual({'data': None, 'literal': None}, result['output'])

    def test_referenced_null_is_not_an_absent_field(self):
        result = core.run_process('mapping', {'data': None})
        self.assertTrue(result['ok'], result)
        self.assertEqual({'data': None}, result['output'])

    def test_nested_arrays_resolve_references_and_keep_positions(self):
        self.process['steps'][0]['input'] = {'data': ['$.left', {'inner': '$.data'}, None, False, 0,
                                                     {'list': ['$.left', '$.data']}]}
        result = core.run_process('mapping', {'left': 3, 'data': None})
        self.assertTrue(result['ok'], result)
        self.assertEqual({'data': [3, {'inner': None}, None, False, 0, {'list': [3, None]}]}, result['output'])

    def test_missing_optional_fields_stay_omitted(self):
        self.process['steps'][0]['input']['extra'] = '$.missing'
        self.process['output']['extra'] = '$.steps.echo.missing'
        result = core.run_process('mapping', {'data': None})
        self.assertTrue(result['ok'], result)
        self.assertEqual({'data': None}, self.dispatch.call_args.args[1])
        self.assertEqual({'data': None}, result['output'])

    def test_referenced_data_is_not_interpreted_as_another_mapping(self):
        data = {'literal': '$.absent', 'items': ['$.absent', None]}
        result = core.run_process('mapping', {'data': data})
        self.assertTrue(result['ok'], result)
        self.assertEqual({'data': data}, result['output'])

    def test_missing_array_entry_fails_before_dispatch_and_is_persisted(self):
        self.process['steps'][0]['input'] = {'data': ['$.missing']}
        result = core.run_process('mapping', {})
        self.assertFalse(result['ok'])
        self.assertIn('input mapping', result['error'])
        self.assertIn('$.missing', result['error'])
        self.dispatch.assert_not_called()
        self.assertEqual(['echo'], [step['id'] for step in result['receipt']['steps']])
        self.assertFalse(result['receipt']['steps'][0]['ok'])
        self.assertEqual('wm_process_runs', self.database.insert.call_args.args[0])
        self.assertFalse(self.database.insert.call_args.args[1]['ok'])
        json.dumps(result, allow_nan=False)

    def test_missing_root_input_reference_fails_before_dispatch(self):
        self.process['steps'][0]['input'] = '$.missing'
        result = core.run_process('mapping', {})
        self.assertFalse(result['ok'])
        self.assertIn('input mapping', result['error'])
        self.dispatch.assert_not_called()

    def test_missing_array_output_fails_with_a_completed_step_receipt(self):
        self.process['output'] = {'data': ['$.steps.echo.absent']}
        result = core.run_process('mapping', {'data': 'ok'})
        self.assertFalse(result['ok'])
        self.assertIn('output mapping', result['error'])
        self.assertIsNone(result['output'])
        self.assertTrue(result['receipt']['steps'][0]['ok'])
        self.assertEqual(result['error'], result['receipt']['error'])
        self.assertEqual(1, self.dispatch.call_count)
        self.assertFalse(self.database.insert.call_args.args[1]['ok'])

    def test_missing_root_output_reference_is_not_a_successful_null(self):
        self.process['output'] = '$.steps.echo.absent'
        result = core.run_process('mapping', {'data': 'ok'})
        self.assertFalse(result['ok'])
        self.assertIn('output mapping', result['error'])
        self.assertIsNone(result['output'])

    def test_explicit_root_output_null_remains_successful(self):
        self.process['output'] = None
        result = core.run_process('mapping', {'data': 'ok'})
        self.assertTrue(result['ok'], result)
        self.assertIsNone(result['output'])

    def test_optional_nonnullable_field_does_not_silently_drop_null(self):
        mapping = {'items': '$.items', 'currency': '$.currency', 'coupon': '$.coupon'}
        data = {'items': [], 'currency': 'PLN'}
        schema = core._schema('pricing.quote', 'input')
        self.assertEqual([], core.validate(core._resolve(mapping, data), schema))
        data['coupon'] = None
        self.assertTrue(core.validate(core._resolve(mapping, data), schema))


if __name__ == "__main__":
    unittest.main()
