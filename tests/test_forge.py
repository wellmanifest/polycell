"""Regeneration is bounded, oracle-bound, and retains useful failures."""
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

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

    def answer(self, source=None, target='generated/cell.py'):
        return {'bundle': {'harness_py': forge.HARNESS, 'kernel_rs': forge.KERNEL,
                           'files': {target: self.source if source is None else source}},
                'metrics': {'request_id': 'test-native-request'}}

    @contextmanager
    def provider(self, **options):
        # Exercise the real adapter without requiring optional provider wheels.
        sandbox = ModuleType('forge_base.sandbox')
        sandbox.run_bounded = Mock(**options)
        runtime = ModuleType('subllm.local_runtime')
        runtime.render_profiles = lambda **kwargs: {'subllm.toml': ''}
        with patch.dict('sys.modules', {'forge_base.sandbox': sandbox, 'subllm.local_runtime': runtime}):
            yield sandbox.run_bounded

    def test_rejected_model_answer_is_retained_and_regenerated(self):
        rejected = [self.answer(target='wrong/cell.py'),
                    self.answer(source=self.source.replace(self.manifest['contract'], 'wrong-contract', 1))]
        for number, answer in enumerate(rejected):
            with self.subTest(answer=answer):
                self.out, self.audit = self.root / f'accepted-{number}', self.root / f'audit-{number}'
                replies = [json.dumps(answer).encode(), json.dumps(self.answer()).encode()]
                with self.provider(side_effect=replies) as provider, \
                     patch.object(forge, 'qualify', side_effect=self.receipt) as qualify:
                    result = self.run_loop(2)
                self.assertEqual(2, result['attempts'])
                self.assertEqual(2, provider.call_count)
                qualify.assert_called_once()
                self.assertEqual(self.source, (self.out / 'cell.py').read_text())
                original = self.audit / 'attempt-001/provider/bundle.json'
                self.assertEqual(answer['bundle'], json.loads(original.read_text()))
                report = json.loads((self.audit / 'report.json').read_text())
                self.assertEqual('proposal_rejected', report['attempts'][0]['stage'])
                second_prompt = json.loads(provider.call_args_list[1].args[1])['prompt']
                self.assertIn(report['attempts'][0]['error'], second_prompt)
                self.assertIn('ENTIRE file', second_prompt)

    def test_rejected_model_answer_exhausts_budget_without_publication(self):
        answer = self.answer(target='wrong/cell.py')
        with self.provider(return_value=json.dumps(answer).encode()) as provider, \
             patch.object(forge, 'qualify') as qualify:
            with self.assertRaisesRegex(ValueError, 'after 2 attempts'):
                self.run_loop(2)
        self.assertEqual(2, provider.call_count)
        qualify.assert_not_called()
        self.assertFalse(self.out.exists())
        for number in (1, 2):
            original = self.audit / f'attempt-{number:03}/provider/bundle.json'
            self.assertEqual(answer['bundle'], json.loads(original.read_text()))

    def test_impure_package_contents_are_retained_and_regenerated(self):
        cases = [('shipping.cost', '\nimport socket\n'),
                 ('notify.render', '\nimport { readFileSync } from "node:fs";\n'),
                 ('pricing.quote', '\nuse std::fs;\n')]
        for number, (selector, addition) in enumerate(cases):
            with self.subTest(language=selector):
                self.base = self.root / f'baseline-{number}'
                self.manifest = package.export(selector, self.base)
                self.source = (self.base / self.manifest['implementation']).read_text()
                self.out, self.audit = self.root / f'accepted-{number}', self.root / f'audit-{number}'
                target = 'generated/' + self.manifest['implementation']
                bad = self.answer(source=self.source + addition, target=target)
                good = self.answer(target=target)
                with self.provider(side_effect=[json.dumps(bad).encode(), json.dumps(good).encode()]) as provider, \
                     patch.object(forge, 'qualify', side_effect=self.receipt) as qualify:
                    result = self.run_loop(2)
                self.assertEqual(2, result['attempts'])
                self.assertEqual(2, provider.call_count)
                qualify.assert_called_once()
                self.assertFalse((self.audit / 'attempt-001/candidate').exists())
                self.assertEqual(self.source, (self.out / self.manifest['implementation']).read_text())
                report = json.loads((self.audit / 'report.json').read_text())
                self.assertEqual('proposal_rejected', report['attempts'][0]['stage'])
                self.assertIn('known I/O', report['attempts'][0]['error'])
                self.assertEqual(bad['bundle'], json.loads((self.audit / 'attempt-001/provider/bundle.json').read_text()))
                prompt = json.loads(provider.call_args_list[1].args[1])['prompt']
                self.assertIn(report['attempts'][0]['error'], prompt)
                self.assertIn('ENTIRE file', prompt)

    def test_oversized_generated_file_can_be_regenerated(self):
        bad = self.answer(source=self.source + '\n#' + 'x' * 2_000_000)
        with self.provider(side_effect=[json.dumps(bad).encode(), json.dumps(self.answer()).encode()]) as provider, \
             patch.object(forge, 'qualify', side_effect=self.receipt) as qualify:
            result = self.run_loop(2)
        self.assertEqual(2, result['attempts'])
        self.assertEqual(2, provider.call_count)
        qualify.assert_called_once()
        self.assertFalse((self.audit / 'attempt-001/candidate').exists())
        self.assertEqual(self.source, (self.out / 'cell.py').read_text())
        report = json.loads((self.audit / 'report.json').read_text())
        self.assertEqual('proposal_rejected', report['attempts'][0]['stage'])
        self.assertIn('bounded regular files', report['attempts'][0]['error'])

    def test_rejected_package_contents_exhaust_attempts_without_qualification(self):
        bad = self.answer(source=self.source + '\nimport socket\n')
        with self.provider(return_value=json.dumps(bad).encode()) as provider, \
             patch.object(forge, 'qualify') as qualify:
            with self.assertRaisesRegex(ValueError, 'after 2 attempts'):
                self.run_loop(2)
        self.assertEqual(2, provider.call_count)
        qualify.assert_not_called()
        self.assertFalse(self.out.exists())
        report = json.loads((self.audit / 'report.json').read_text())
        self.assertFalse(report['ok'])
        self.assertEqual(['proposal_rejected', 'proposal_rejected'], [a['stage'] for a in report['attempts']])
        for number in (1, 2):
            self.assertFalse((self.audit / f'attempt-{number:03}/candidate').exists())
            self.assertEqual(bad['bundle'], json.loads((self.audit / f'attempt-{number:03}/provider/bundle.json').read_text()))

    def test_package_write_failure_stops_without_retry(self):
        with self.provider(return_value=json.dumps(self.answer()).encode()) as provider, \
             patch.object(forge, 'replace', side_effect=PermissionError('injected write failure')), \
             patch.object(forge, 'qualify') as qualify:
            with self.assertRaisesRegex(ValueError, 'generation failed'):
                self.run_loop(2)
        provider.assert_called_once()
        qualify.assert_not_called()
        self.assertFalse(self.out.exists())
        report = json.loads((self.audit / 'report.json').read_text())
        self.assertEqual('proposal', report['attempts'][0]['stage'])
        self.assertIn('injected write failure', report['attempts'][0]['error'])

    def test_package_destination_collision_stops_and_preserves_existing_data(self):
        occupied = self.audit / 'attempt-001/candidate'
        def reply(*args, **kwargs):
            occupied.mkdir()
            (occupied / 'existing-data').write_text('preserve')
            return json.dumps(self.answer()).encode()
        with self.provider(side_effect=reply) as provider, patch.object(forge, 'qualify') as qualify:
            with self.assertRaisesRegex(ValueError, 'generation failed'):
                self.run_loop(2)
        provider.assert_called_once()
        qualify.assert_not_called()
        self.assertEqual('preserve', (occupied / 'existing-data').read_text())
        self.assertFalse(self.out.exists())
        report = json.loads((self.audit / 'report.json').read_text())
        self.assertEqual('proposal', report['attempts'][0]['stage'])
        self.assertIn('destination already exists', report['attempts'][0]['error'])

    def test_actual_provider_error_answer_stops_without_retry(self):
        answer = {'error': 'provider unavailable', 'metrics': {'request_id': 'failed-request'}}
        with self.provider(return_value=json.dumps(answer).encode()) as provider, \
             patch.object(forge, 'qualify') as qualify:
            with self.assertRaisesRegex(ValueError, 'generation failed'):
                self.run_loop(2)
        provider.assert_called_once()
        qualify.assert_not_called()
        self.assertFalse(self.out.exists())
        self.assertIn('provider unavailable', (self.audit / 'report.json').read_text())

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

    def proposal_case(self, name):
        here = self.root / name
        self.base = here / 'baseline'
        self.manifest = package.export('shipping.cost', self.base)
        self.source = (self.base / 'cell.py').read_text()
        self.out, self.audit = here / 'candidate', here / 'audit'

    def proposal_tree(self):
        return {str(p.relative_to(self.root)): ('link', str(p.readlink())) if p.is_symlink()
                else ('file', p.read_bytes()) if p.is_file() else ('directory',)
                for p in self.root.rglob('*')}

    def reject_proposal_paths(self, message):
        before = self.proposal_tree()
        with self.provider(return_value=json.dumps(self.answer()).encode()) as provider:
            with self.assertRaisesRegex(ValueError, message):
                forge.propose(self.base, self.out, self.audit, 'fixture', 'http://localhost',
                              'Regenerate the entire file')
            provider.assert_not_called()
        self.assertEqual(before, self.proposal_tree())
        package.verify(self.base)

    def test_proposal_paths_cannot_add_output_or_audit_to_baseline(self):
        for target in ('output', 'audit'):
            with self.subTest(target=target):
                self.proposal_case(target)
                if target == 'output':
                    self.out = self.base / 'candidate'
                else:
                    self.audit = self.base / 'audit'
                self.reject_proposal_paths('outside the source packages')

    def test_proposal_paths_require_disjoint_output_and_audit(self):
        for relation in ('same', 'audit-in-output', 'output-in-audit'):
            with self.subTest(relation=relation):
                self.proposal_case(relation)
                if relation == 'same':
                    self.audit = self.out
                elif relation == 'audit-in-output':
                    self.audit = self.out / 'audit'
                else:
                    self.out = self.audit / 'candidate'
                self.reject_proposal_paths('destinations must be disjoint')

    def test_proposal_paths_resolve_parent_aliases_before_effects(self):
        for relation in ('source-alias', 'destination-alias'):
            with self.subTest(relation=relation):
                self.proposal_case(relation)
                alias = self.base.parent / 'alias'
                if relation == 'source-alias':
                    alias.symlink_to(self.base, target_is_directory=True)
                    self.audit = alias / 'audit'
                    message = 'outside the source packages'
                else:
                    alias.symlink_to(self.base.parent, target_is_directory=True)
                    self.out = alias / 'audit/candidate'
                    message = 'destinations must be disjoint'
                self.reject_proposal_paths(message)

    def test_proposal_paths_preserve_occupied_and_dangling_destinations(self):
        for target in ('output', 'audit'):
            for kind in ('file', 'directory', 'dangling-link'):
                with self.subTest(target=target, kind=kind):
                    self.proposal_case(target + '-' + kind)
                    path = self.out if target == 'output' else self.audit
                    if kind == 'file':
                        path.write_text('preserve existing data')
                    elif kind == 'directory':
                        path.mkdir()
                        (path / 'existing').write_text('preserve existing data')
                    else:
                        path.symlink_to(path.parent / 'missing-target')
                    self.reject_proposal_paths('destinations must be new')

    def test_proposal_paths_allow_disjoint_complete_files_in_each_language(self):
        for selector in ('shipping.cost', 'notify.render', 'pricing.quote'):
            with self.subTest(selector=selector):
                here = self.root / selector
                self.base = here / 'baseline'
                self.manifest = package.export(selector, self.base)
                self.source = (self.base / self.manifest['implementation']).read_text()
                before = {p.name: p.read_bytes() for p in self.base.iterdir()}
                out, audit = here / 'nested/candidate', here / 'separate/audit'
                answer = self.answer(target='generated/' + self.manifest['implementation'])
                with self.provider(return_value=json.dumps(answer).encode()) as provider:
                    result = forge.propose(self.base, out, audit, 'fixture', 'http://localhost',
                                           'Regenerate the entire file')
                provider.assert_called_once()
                self.assertEqual('required', result['qualification'])
                self.assertEqual(self.source, (out / self.manifest['implementation']).read_text())
                self.assertEqual(before, {p.name: p.read_bytes() for p in self.base.iterdir()})
                self.assertEqual(answer['bundle'], json.loads((audit / 'bundle.json').read_text()))
                self.assertEqual('test-native-request', json.loads((audit / 'metrics.json').read_text())['request_id'])
                package.verify(out)

    def test_proposal_paths_keep_regeneration_alias_rejection_before_snapshots(self):
        alias = self.root / 'baseline-alias'
        alias.symlink_to(self.base, target_is_directory=True)
        self.audit = alias / 'audit'
        before = self.proposal_tree()
        with patch.object(forge, 'snapshot') as snapshots, patch.object(forge, 'propose') as proposals:
            with self.assertRaisesRegex(ValueError, 'outside the source packages'):
                self.run_loop()
            snapshots.assert_not_called()
            proposals.assert_not_called()
        self.assertEqual(before, self.proposal_tree())


class QualificationDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.case = {'name': 'boundary', 'output': {'result': 19.99}}
        self.meta = {'contract': 'expected', 'urn': 'urn:wm:cell:test:example:v1', 'owner': 'python'}
        self.validator = Draft202012Validator({'type': 'object', 'required': ['result'],
                                               'properties': {'result': {'type': 'number'}}})

    def validate(self, reply):
        reply = {'urn': self.meta['urn'], 'lang': self.meta['owner'], 'ok': True, 'error': '',
                 'duration_ms': 0, 'contract': self.meta['contract'], 'output': self.case['output'], **reply}
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
