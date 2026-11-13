"""Package boundary regressions: no inference, Docker or external Forge checkout."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from tools.polycell import package
from tools.polycell.forge import HARNESS, KERNEL, extract, request, stamp_header


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'base'
        self.manifest = package.export('shipping.cost', self.base)

    def update_artifact(self, directory, name, value):
        payload = package.json_bytes(value)
        (directory / name).write_bytes(payload)
        manifest = json.loads((directory / 'package.json').read_text())
        manifest['files'][name] = package.digest(payload)
        (directory / 'package.json').write_bytes(package.json_bytes(manifest))

    def update_contract(self, directory, contract):
        manifest = json.loads((directory / 'package.json').read_text())
        old_hash = manifest['contract']
        manifest['contract'] = package.interface_hash(contract)
        (directory / 'contract.cell.yaml').write_text(yaml.safe_dump(contract))
        source = directory / manifest['implementation']
        source.write_text(source.read_text().replace(old_hash, manifest['contract']))
        for name in manifest['files']:
            manifest['files'][name] = package.digest((directory / name).read_bytes())
        (directory / 'package.json').write_bytes(package.json_bytes(manifest))

    def test_all_languages_export_one_source(self):
        for cell, ext in (('customer.validate', '.py'), ('notify.render', '.ts'), ('pricing.quote', '.rs')):
            dest = self.root / cell
            package.export(cell, dest)
            package.verify(dest)
            sources = [p.name for p in dest.iterdir() if p.suffix in ('.py', '.ts', '.rs')]
            self.assertEqual(['cell' + ext], sources)

    def test_changed_source_digest_rejected(self):
        (self.base / 'cell.py').write_text('# changed\n')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            package.verify(self.base)

    def test_extra_source_rejected(self):
        (self.base / 'helper.py').write_text('x = 1\n')
        with self.assertRaisesRegex(ValueError, 'unlisted'):
            package.verify(self.base)

    def test_symlink_rejected(self):
        (self.base / 'cell.py').unlink()
        (self.base / 'cell.py').symlink_to(Path(__file__).resolve())
        with self.assertRaisesRegex(ValueError, 'regular files'):
            package.verify(self.base)

    def test_no_overwrite(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            package.export('shipping.cost', self.base)

    def test_stale_header_rejected_even_with_updated_digest(self):
        code = (self.base / 'cell.py').read_text().replace(self.manifest['contract'], '000000000000')
        dest = self.root / 'stale'
        with self.assertRaisesRegex(ValueError, 'stale'):
            package.replace(self.base, code, dest)
        self.assertFalse(dest.exists())

    def test_known_io_rejected(self):
        code = (self.base / 'cell.py').read_text() + '\nimport socket\n'
        with self.assertRaisesRegex(ValueError, 'I/O'):
            package.replace(self.base, code, self.root / 'impure')

    def test_oracle_cannot_be_changed_with_candidate(self):
        dest = self.root / 'candidate'
        package.replace(self.base, (self.base / 'cell.py').read_text(), dest)
        cases = json.loads((dest / 'cases.json').read_text())
        # Change a golden case, while preserving every example from the contract.
        next(case for case in cases if ':golden' in case['name'])['output']['result'] = 123.0
        payload = package.json_bytes(cases)
        (dest / 'cases.json').write_bytes(payload)
        manifest = json.loads((dest / 'package.json').read_text())
        manifest['files']['cases.json'] = package.digest(payload)
        (dest / 'package.json').write_bytes(package.json_bytes(manifest))
        package.verify(dest)
        with self.assertRaisesRegex(ValueError, 'trusted artifact'):
            package.check_oracle(dest, self.base)

    def test_cases_cannot_override_or_omit_contract_examples(self):
        original = json.loads((self.base / 'cases.json').read_text())
        changed = copy.deepcopy(original)
        changed[0]['output']['result'] = 123.0
        for cases in (changed, original[1:]):
            with self.subTest(cases=len(cases)):
                self.update_artifact(self.base, 'cases.json', cases)
                with self.assertRaisesRegex(ValueError, 'preserve contract example'):
                    package.verify(self.base)

    def test_cases_require_matching_identity_and_unique_names(self):
        original = json.loads((self.base / 'cases.json').read_text())
        for field, value in (('urn', 'urn:wm:cell:other:shipping.cost:v1'), ('owner', 'ts'), ('name', original[1]['name'])):
            with self.subTest(field=field):
                cases = copy.deepcopy(original)
                cases[0][field] = value
                self.update_artifact(self.base, 'cases.json', cases)
                with self.assertRaisesRegex(ValueError, 'identity|duplicate'):
                    package.verify(self.base)

    def test_package_schema_cannot_weaken_contract(self):
        self.update_artifact(self.base, 'output.schema.json', {})
        with self.assertRaisesRegex(ValueError, 'schema does not match contract'):
            package.verify(self.base)

    def test_contract_types_must_be_self_contained(self):
        contract = yaml.safe_load((self.base / 'contract.cell.yaml').read_text())
        contract['input']['extra'] = 'Missing?'
        self.update_contract(self.base, contract)
        with self.assertRaisesRegex(ValueError, 'unknown type'):
            package.verify(self.base)

    def test_contract_name_must_match_urn(self):
        contract = yaml.safe_load((self.base / 'contract.cell.yaml').read_text())
        contract['name'] = 'different.name'
        self.update_contract(self.base, contract)
        manifest = json.loads((self.base / 'package.json').read_text())
        manifest['name'] = contract['name']
        (self.base / 'package.json').write_bytes(package.json_bytes(manifest))
        with self.assertRaisesRegex(ValueError, 'name does not match URN'):
            package.verify(self.base)

    def test_missing_manifest_reports_package_error(self):
        (self.base / 'package.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing package.json'):
            package.verify(self.base)

    def test_git_bundle_roundtrip(self):
        bundle = self.root / 'shipping.bundle'
        commit = package.git_snapshot(self.base, bundle)
        for default_branch in ('master', 'main', 'custom-default'):
            with self.subTest(default_branch=default_branch):
                clone = self.root / ('clone-' + default_branch)
                subprocess.run(['git', '-c', 'init.defaultBranch=' + default_branch,
                                'clone', '--quiet', str(bundle), str(clone)], check=True)
                self.assertEqual(self.manifest, package.verify(clone))
                self.assertEqual(commit, subprocess.check_output(['git', '-C', str(clone), 'rev-parse', 'HEAD'], text=True).strip())

    def test_bundle_cannot_overwrite_or_live_inside_package(self):
        for bundle in (self.base / 'self.bundle', self.base / 'cell.py'):
            with self.assertRaisesRegex(ValueError, 'outside'):
                package.git_snapshot(self.base, bundle)

    def test_git_bundle_includes_files_ignored_by_global_configuration(self):
        excludes = self.root / 'global-ignore'
        excludes.write_text('cell.py\nREADME.md\n')
        bundle = self.root / 'complete.bundle'
        with patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.excludesFile',
                                     'GIT_CONFIG_VALUE_0': str(excludes)}):
            package.git_snapshot(self.base, bundle)
        clone = self.root / 'clone'
        subprocess.run(['git', 'clone', '--quiet', str(bundle), str(clone)], check=True)
        self.assertEqual(self.manifest, package.verify(clone))

    def test_duplicate_cell_rejected_before_assembly(self):
        dest = self.root / 'app'
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            package.assemble([self.base, self.base], dest)
        self.assertFalse(dest.exists())

    def test_assembly_records_commit_and_manifest_digest(self):
        commit = package.git_snapshot(self.base)
        out = self.root / 'app'
        lock = package.assemble([self.base], out)
        self.assertEqual(commit, lock['packages'][0]['git_commit'])
        self.assertEqual(package.digest((self.base / 'package.json').read_bytes()), lock['packages'][0]['manifest_sha256'])
        self.assertEqual((self.base / 'cell.py').read_bytes(), (out / 'cells/python/shipping_cost.py').read_bytes())
        self.assertEqual(1, len(list((out / 'contracts/cells').glob('*.yaml'))))

    def test_failed_assembly_leaves_no_destination_and_can_be_retried(self):
        package.git_snapshot(self.base)
        self.update_artifact(self.base, 'provider.json', {'note': 'uncommitted artifact'})
        out = self.root / 'app'
        with self.assertRaisesRegex(ValueError, 'must be committed'):
            package.assemble([self.base], out)
        self.assertFalse(out.exists())
        package.assemble([self.base], out, record_git=False)
        self.assertTrue((out / 'cellset.lock.json').is_file())

    def test_assembled_agent_rules_work_without_repository_governance(self):
        out = self.root / 'portable-app'
        package.assemble([self.base], out, record_git=False)
        rules = (out / 'AGENTS.md').read_text()
        self.assertIn('make check', rules)
        self.assertIn('make parity', rules)
        self.assertIn('run(input) -> output', rules)
        self.assertNotIn('.governance/', rules)
        self.assertFalse((out / '.governance').exists())

    def test_assembly_preserves_legacy_runtime_agent_rules(self):
        runtime = self.root / 'legacy-runtime'
        runtime.mkdir()
        rules = 'Run make check and make parity before publishing.\n'
        (runtime / 'AGENTS.md').write_text(rules)
        out = self.root / 'legacy-app'
        package.assemble([self.base], out, runtime=runtime, record_git=False)
        self.assertEqual(rules, (out / 'AGENTS.md').read_text())

    def test_generator_failure_does_not_publish_partial_application(self):
        out = self.root / 'app'
        with patch.object(package.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'gen')):
            with self.assertRaises(subprocess.CalledProcessError):
                package.assemble([self.base], out, generate=True)
        self.assertFalse(out.exists())
        self.assertFalse(list(self.root.glob('.app-*')))

    def test_assembly_rejects_conflicting_shared_types(self):
        pricing = self.root / 'pricing'
        package.export('pricing.quote', pricing)
        declared = yaml.safe_load((pricing / 'contract.cell.yaml').read_text())['types']
        name = next(iter(declared))
        contract = yaml.safe_load((self.base / 'contract.cell.yaml').read_text())
        contract['types'] = {name: {'other': 'string'}}
        self.update_contract(self.base, contract)
        for kind in ('input', 'output'):
            schema = json.loads((self.base / (kind + '.schema.json')).read_text())
            schema['$defs'][name] = {'type': 'object', 'additionalProperties': False,
                                     'properties': {'other': {'type': 'string'}}, 'required': ['other']}
            self.update_artifact(self.base, kind + '.schema.json', schema)
        package.verify(self.base)
        out = self.root / 'app'
        with self.assertRaisesRegex(ValueError, 'conflicting shared type'):
            package.assemble([self.base, pricing], out)
        self.assertFalse(out.exists())

    def test_qualification_receipt_uses_frozen_artifacts(self):
        package.git_snapshot(self.base)
        original = (self.base / 'package.json').read_bytes()
        def evaluate(candidate, oracle, image, timeout):
            self.assertFalse((candidate / '.git').exists())
            self.update_artifact(self.base, 'provider.json', {'note': 'changed during evaluation'})
            self.assertEqual(self.manifest, package.check_oracle(candidate, oracle))
            return {'candidate_sha256': package.digest((candidate / 'package.json').read_bytes())}
        with patch.object(package, '_qualify_snapshot', side_effect=evaluate):
            receipt = package.qualify(self.base, self.base, 'test-image')
        self.assertEqual(package.digest(original), receipt['candidate_sha256'])
        self.assertNotEqual(package.digest((self.base / 'package.json').read_bytes()), receipt['candidate_sha256'])

    def test_forge_request_uses_contract_context_without_old_implementation(self):
        req = request(self.base, 'Regenerate')
        self.assertIn('Przypadki golden', req['prompt'])
        self.assertNotIn('RATES =', req['prompt'])
        self.assertEqual({'harness.py': HARNESS, 'kernel.rs': KERNEL}, req['baseline'])

    def test_forge_cannot_modify_scaffolding_or_add_helpers(self):
        bundle = {'harness_py': HARNESS, 'kernel_rs': KERNEL, 'files': {'generated/cell.py': 'complete source'}, 'rationale': 'test'}
        self.assertEqual('complete source', extract(bundle, self.manifest))
        for key in ('harness_py', 'kernel_rs', 'files'):
            changed = copy.deepcopy(bundle)
            if key == 'files':
                changed[key]['generated/helper.py'] = 'extra'
            else:
                changed[key] += 'changed'
            with self.assertRaises(ValueError):
                extract(changed, self.manifest)

    def test_controller_stamps_metadata_without_changing_body(self):
        code = (self.base / 'cell.py').read_text()
        self.assertEqual(code, stamp_header(code, self.manifest))
        self.assertEqual(code, stamp_header(code.replace('# polycell:', '# python:', 1), self.manifest))
        self.assertEqual(code, stamp_header(code.split('\n', 1)[1], self.manifest))

    def test_controller_does_not_relabel_another_contract(self):
        code = (self.base / 'cell.py').read_text().replace(self.manifest['contract'], '000000000000')
        with self.assertRaisesRegex(ValueError, 'different contract'):
            stamp_header(code, self.manifest)


if __name__ == '__main__':
    unittest.main()
