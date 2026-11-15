"""Replay must retain the archived acceptance context without new inference."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from tools.polycell import forge, package


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prepare('shipping.cost', 'default')

    def prepare(self, selector, name):
        here = self.root / name
        self.base, self.audit, self.out = here / 'baseline', here / 'audit', here / "replayed O'Brien żółć"
        self.meta = package.export(selector, self.base)
        self.source = (self.base / self.meta['implementation']).read_text()
        self.audit.mkdir()
        self.request_id = 'replay-fixture-' + name
        (self.audit / 'metrics.json').write_bytes(package.json_bytes({'request_id': self.request_id}))
        with sqlite3.connect(self.audit / 'usage.sqlite3') as db:
            # Minimal read-side fixture; real native archives are exercised separately.
            db.execute('create table attempts (request_id text, status text, archive_id text, archive_day text)')
            db.execute('insert into attempts values (?, ?, ?, ?)',
                       (hashlib.sha256(self.request_id.encode()).hexdigest()[:24], 'success', 'saved', '2026-11-15'))
        self.original = {'objective': forge.request(self.base, 'Regenerate the entire file')['prompt'],
                         'baseline': {'harness.py': forge.HARNESS, 'kernel.rs': forge.KERNEL}}
        self.bundle = {'harness_py': forge.HARNESS, 'kernel_rs': forge.KERNEL,
                       'files': {'generated/' + self.meta['implementation']: self.source}, 'rationale': 'Fixture'}
        self.saved = {'correlation_id': self.request_id,
                      'request': {'messages': [{}, {'content': json.dumps(self.original)}]},
                      'response': {'content': json.dumps(self.bundle)}}

    @contextmanager
    def archive(self, retrieve=None):
        providers, interactions = ModuleType('forge_base.providers'), ModuleType('subllm.interaction_store')
        providers.validate_bundle = Mock(side_effect=lambda value: value)
        instance = Mock()
        instance.get_interaction.side_effect = retrieve or (lambda *args: self.saved)
        interactions.InteractionStore = Mock(return_value=instance)
        with patch.dict('sys.modules', {'forge_base.providers': providers,
                                       'subllm.interaction_store': interactions}):
            yield interactions.InteractionStore, providers.validate_bundle

    def tree(self, root=None):
        root = root or self.root
        return {str(p.relative_to(root)): ('link', str(p.readlink())) if p.is_symlink()
                else ('file', p.read_bytes()) if p.is_file() else ('directory',)
                for p in root.rglob('*')}

    def replay(self):
        return forge.replay(self.base, self.out, self.audit)

    def change_cases(self):
        cases = json.loads((self.base / 'cases.json').read_text())
        next(case for case in cases if ':golden' in case['name'])['output']['result'] += 1
        payload = package.json_bytes(cases)
        (self.base / 'cases.json').write_bytes(payload)
        meta = json.loads((self.base / 'package.json').read_text())
        meta['files']['cases.json'] = package.digest(payload)
        (self.base / 'package.json').write_bytes(package.json_bytes(meta))
        package.verify(self.base)

    def reject_context(self):
        before = self.tree()
        with self.archive() as (_, validate):
            with self.assertRaisesRegex(ValueError, 'package context|different Forge baseline'):
                self.replay()
            validate.assert_not_called()
        self.assertEqual(before, self.tree())

    def test_exact_archived_context_replays_all_languages_without_journal_writes(self):
        for selector in ('shipping.cost', 'notify.render', 'pricing.quote'):
            with self.subTest(selector=selector):
                self.prepare(selector, selector)
                source, audit = self.tree(self.base), self.tree(self.audit)
                with self.archive() as (store, validate):
                    result = self.replay()
                store.assert_called_once_with(self.audit / 'archive')
                validate.assert_called_once()
                self.assertEqual('required', result['qualification'])
                self.assertIs(result['metrics']['replay'], True)
                self.assertEqual(0, result['metrics']['new_inference_calls'])
                self.assertEqual(self.source, (self.out / self.meta['implementation']).read_text())
                self.assertEqual(source, self.tree(self.base))
                self.assertEqual(audit, self.tree(self.audit))
                package.verify(self.out)

    def test_changed_acceptance_cases_cannot_reuse_an_unchanged_prompt(self):
        prompt = (self.base / 'prompt.md').read_bytes()
        self.change_cases()
        self.assertEqual(prompt, (self.base / 'prompt.md').read_bytes())
        self.reject_context()

    def test_prompt_embedded_in_an_unrelated_objective_is_not_a_context_binding(self):
        self.original['objective'] = 'Unrelated request\n' + (self.base / 'prompt.md').read_text()
        self.saved['request']['messages'][1]['content'] = json.dumps(self.original)
        self.reject_context()

    def test_correlation_and_forge_baseline_are_still_required(self):
        for field in ('correlation', 'baseline'):
            with self.subTest(field=field):
                self.prepare('shipping.cost', field)
                if field == 'correlation':
                    self.saved['correlation_id'] = 'another-request'
                else:
                    self.original['baseline']['kernel.rs'] = 'different baseline'
                    self.saved['request']['messages'][1]['content'] = json.dumps(self.original)
                self.reject_context()

    def test_arbitrary_original_objective_suffix_remains_valid(self):
        self.original['objective'] = forge.request(self.base, 'A different objective\nwith Unicode żółć')['prompt']
        self.saved['request']['messages'][1]['content'] = json.dumps(self.original)
        with self.archive():
            self.replay()
        package.verify(self.out)

    def test_output_cannot_modify_package_or_audit_including_parent_aliases(self):
        for target in ('package', 'audit', 'package-alias', 'audit-alias'):
            with self.subTest(target=target):
                self.prepare('shipping.cost', target)
                source = self.base if target.startswith('package') else self.audit
                if target.endswith('alias'):
                    alias = source.parent / 'alias'
                    alias.symlink_to(source, target_is_directory=True)
                    source = alias
                self.out = source / 'new-output'
                before = self.tree()
                with self.archive() as (store, validate):
                    with self.assertRaisesRegex(ValueError, 'outside.*package.*audit'):
                        self.replay()
                    store.assert_not_called()
                    validate.assert_not_called()
                self.assertEqual(before, self.tree())

    def test_occupied_or_dangling_output_is_preserved_before_archive_access(self):
        for kind in ('file', 'directory', 'dangling-link'):
            with self.subTest(kind=kind):
                self.prepare('shipping.cost', kind)
                if kind == 'file':
                    self.out.write_text('preserve data')
                elif kind == 'directory':
                    self.out.mkdir()
                    (self.out / 'existing').write_text('preserve data')
                else:
                    self.out.symlink_to(self.out.parent / 'missing')
                before = self.tree()
                with self.archive() as (store, _):
                    with self.assertRaisesRegex(ValueError, 'destination must be new'):
                        self.replay()
                    store.assert_not_called()
                self.assertEqual(before, self.tree())

    def test_concurrent_input_change_cannot_relabel_the_archived_snapshot(self):
        original = (self.base / 'cases.json').read_bytes()
        def retrieve(*args):
            self.change_cases()
            return self.saved
        with self.archive(retrieve):
            self.replay()
        self.assertNotEqual(original, (self.base / 'cases.json').read_bytes())
        self.assertEqual(original, (self.out / 'cases.json').read_bytes())
        package.verify(self.out)

    def test_failed_output_write_does_not_publish_a_partial_package(self):
        before = self.tree()
        def partial(base, code, out, metrics):
            out.mkdir(parents=True)
            (out / 'partial').write_text('incomplete')
            raise OSError('injected write failure')
        with self.archive(), patch.object(forge, 'replace', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'injected write failure'):
                self.replay()
        self.assertFalse(self.out.exists())
        self.assertEqual(before, self.tree())


if __name__ == '__main__':
    unittest.main()
