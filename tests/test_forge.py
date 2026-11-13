"""Regeneration is bounded, oracle-bound, and retains useful failures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from tools.polycell import forge, package
from tools.polycell.package_worker import validate_reply


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'baseline'
        self.manifest = package.export('shipping.cost', self.base)
        self.source = (self.base / 'cell.py').read_text()
        self.out, self.audit = self.root / 'accepted', self.root / 'audit'

    def propose(self, baseline, candidate, audit, model, url, objective, timeout, reasoning):
        package.replace(baseline, self.source, candidate, {'request_id': 'test-native-request'})

    def receipt(self, candidate, oracle, image):
        package.check_oracle(candidate, oracle)
        return {'ok': True, 'candidate_sha256': package.digest((candidate / 'package.json').read_bytes())}

    def run_loop(self, attempts=3):
        return forge.regenerate(self.base, self.out, self.audit, 'test-model', 'http://localhost',
                                'Regenerate the whole function', self.base, 'test-image', attempts)

    def test_feedback_regenerates_whole_file_and_accepts_only_qualified_result(self):
        calls = []
        def qualify(candidate, oracle, image):
            calls.append(candidate)
            if len(calls) == 1:
                # Caller-side changes after admission cannot change the frozen inputs.
                (self.base / 'cases.json').write_text('[]')
                raise ValueError('pl_over_boundary: host error: AttributeError: dict has no attribute country')
            self.assertNotEqual(self.base, oracle)
            return self.receipt(candidate, oracle, image)
        with patch.object(forge, 'propose', side_effect=self.propose) as proposals, \
             patch.object(forge, 'qualify', side_effect=qualify):
            result = self.run_loop()
        self.assertEqual(2, result['attempts'])
        self.assertIn('host error: AttributeError', proposals.call_args_list[1].args[5])
        self.assertEqual(self.source, (self.out / 'cell.py').read_text())
        self.assertEqual(2, len(calls))
        self.assertTrue(json.loads((self.audit / 'report.json').read_text())['ok'])
        package.verify(self.out)

    def test_exhaustion_leaves_no_public_candidate(self):
        with patch.object(forge, 'propose', side_effect=self.propose) as proposals, \
             patch.object(forge, 'qualify', side_effect=ValueError('behavior mismatch: boundary')):
            with self.assertRaisesRegex(ValueError, 'after 2 attempts'):
                self.run_loop(2)
        self.assertEqual(2, proposals.call_count)
        self.assertFalse(self.out.exists())
        report = json.loads((self.audit / 'report.json').read_text())
        self.assertFalse(report['ok'])
        self.assertEqual(2, len(report['attempts']))
        self.assertTrue((self.audit / 'attempt-001/candidate/cell.py').exists())

    def test_provider_failure_stops_without_repeating_calls(self):
        for error_type in (ValueError, RuntimeError, OSError):
            with self.subTest(error_type=error_type):
                self.audit = self.root / error_type.__name__
                with patch.object(forge, 'propose', side_effect=error_type('provider unavailable')) as proposals, \
                     patch.object(forge, 'qualify') as qualify:
                    with self.assertRaisesRegex(ValueError, 'generation failed'):
                        self.run_loop()
                self.assertEqual(1, proposals.call_count)
                qualify.assert_not_called()
                self.assertFalse(self.out.exists())
                self.assertIn('provider unavailable', (self.audit / 'report.json').read_text())

    def test_publication_rejects_candidate_hash_mismatch(self):
        with patch.object(forge, 'propose', side_effect=self.propose), \
             patch.object(forge, 'qualify', return_value={'ok': True, 'candidate_sha256': 'wrong'}):
            with self.assertRaisesRegex(ValueError, 'changed after qualification'):
                self.run_loop()
        self.assertFalse(self.out.exists())

    def test_invalid_budget_or_paths_fail_before_inference(self):
        with patch.object(forge, 'propose') as proposals:
            for attempts in (0, 4, True):
                with self.subTest(attempts=attempts), self.assertRaises(ValueError):
                    self.run_loop(attempts)
            self.out = self.base / 'inside'
            with self.assertRaisesRegex(ValueError, 'outside'):
                self.run_loop()
            self.out, self.audit = self.root / 'candidate', self.root / 'candidate/audit'
            with self.assertRaisesRegex(ValueError, 'disjoint'):
                self.run_loop()
            proposals.assert_not_called()


class QualificationDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.case = {'name': 'boundary', 'output': {'result': 19.99}}
        self.meta = {'contract': 'expected'}
        self.validator = Draft202012Validator({'type': 'object', 'required': ['result'],
                                               'properties': {'result': {'type': 'number'}}})

    def validate(self, reply):
        validate_reply(self.case, reply, self.meta, self.validator, lambda a, b: a == b)

    def test_host_failure_is_not_hidden_by_output_schema(self):
        with self.assertRaisesRegex(ValueError, 'boundary: host error: AttributeError'):
            self.validate({'ok': False, 'output': None, 'error': 'AttributeError: dict has no attribute country'})

    def test_schema_contract_and_behavior_have_actionable_diagnostics(self):
        for reply, message in [
            ({'ok': True, 'contract': 'wrong', 'output': {'result': 19.99}}, 'contract mismatch'),
            ({'ok': True, 'contract': 'expected', 'output': None}, 'output contract'),
            ({'ok': True, 'contract': 'expected', 'output': {'result': 49.99}}, 'expected.*19.99.*got.*49.99'),
        ]:
            with self.subTest(reply=reply), self.assertRaisesRegex(ValueError, message):
                self.validate(reply)
        self.validate({'ok': True, 'contract': 'expected', 'output': {'result': 19.99}})


if __name__ == '__main__':
    unittest.main()
