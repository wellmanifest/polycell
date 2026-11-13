"""Package boundary regressions: no inference, Docker or external Forge checkout."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.polycell import package
from tools.polycell.forge import HARNESS, KERNEL, extract, request, stamp_header


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'base'
        self.manifest = package.export('shipping.cost', self.base)

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
        cases[0]['output']['result'] = 123.0
        payload = package.json_bytes(cases)
        (dest / 'cases.json').write_bytes(payload)
        manifest = json.loads((dest / 'package.json').read_text())
        manifest['files']['cases.json'] = package.digest(payload)
        (dest / 'package.json').write_bytes(package.json_bytes(manifest))
        package.verify(dest)
        with self.assertRaisesRegex(ValueError, 'trusted artifact'):
            package.check_oracle(dest, self.base)

    def test_git_bundle_roundtrip(self):
        bundle = self.root / 'shipping.bundle'
        commit = package.git_snapshot(self.base, bundle)
        clone = self.root / 'clone'
        subprocess.run(['git', 'clone', '--quiet', str(bundle), str(clone)], check=True)
        self.assertEqual(self.manifest, package.verify(clone))
        self.assertEqual(commit, subprocess.check_output(['git', '-C', str(clone), 'rev-parse', 'HEAD'], text=True).strip())

    def test_bundle_cannot_overwrite_or_live_inside_package(self):
        for bundle in (self.base / 'self.bundle', self.base / 'cell.py'):
            with self.assertRaisesRegex(ValueError, 'outside'):
                package.git_snapshot(self.base, bundle)

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
