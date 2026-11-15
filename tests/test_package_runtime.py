"""Runtime copying must not traverse its own transactional assembly output."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.polycell import package


class RuntimeCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'package'
        self.meta = package.export('shipping.cost', self.base)
        self.before = {p.name: p.read_bytes() for p in self.base.iterdir()}

    @contextmanager
    def bounded_copying(self):
        copytree = shutil.copytree
        calls = []
        def copy(source, destination, *args, **options):
            calls.append((Path(source), Path(destination)))
            # Bound the unfixed regression, rather than exhaust disk/path limits.
            if len(calls) > 4:
                raise AssertionError('runtime copier recursively entered its staging tree')
            return copytree(source, destination, *args, **options)
        with patch.object(package.shutil, 'copytree', side_effect=copy):
            yield calls

    def reject(self, runtime, out, warm=False):
        with self.bounded_copying(), self.assertRaisesRegex(ValueError, 'copied runtime'):
            package.assemble([self.base], out, runtime=runtime, warm=warm)
        self.assertFalse(out.exists())
        self.assertFalse(list(out.parent.glob('.application-*')))
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.base.iterdir()})
        package.verify(self.base)

    def test_output_inside_each_copied_runtime_root_is_rejected(self):
        for name in package.RUNTIME_DIRS:
            with self.subTest(directory=name):
                runtime = self.root / ('runtime-' + name)
                source = runtime / name
                source.mkdir(parents=True)
                (source / 'payload.txt').write_text('preserve')
                self.reject(runtime, source / 'application')
                self.assertEqual(['payload.txt'], sorted(p.name for p in source.iterdir()))
                self.assertEqual('preserve', (source / 'payload.txt').read_text())

    def test_output_parent_alias_cannot_hide_overlap(self):
        runtime = self.root / 'runtime'
        source = runtime / 'tools'
        source.mkdir(parents=True)
        (source / 'payload.txt').write_text('preserve')
        alias = self.root / 'alias'
        alias.symlink_to(source, target_is_directory=True)
        self.reject(runtime, alias / 'application')
        self.assertTrue(alias.is_symlink())
        self.assertEqual(['payload.txt'], sorted(p.name for p in source.iterdir()))

    def test_nested_runtime_alias_cannot_traverse_output_staging(self):
        runtime = self.root / 'runtime'
        (runtime / 'tools').mkdir(parents=True)
        external = self.root / 'external'
        external.mkdir()
        (external / 'payload.txt').write_text('preserve')
        (runtime / 'tools/linked').symlink_to(external, target_is_directory=True)
        self.reject(runtime, external / 'application')
        self.assertTrue((runtime / 'tools/linked').is_symlink())
        self.assertEqual(['payload.txt'], sorted(p.name for p in external.iterdir()))

    def test_normal_output_in_runtime_dot_run_remains_supported(self):
        runtime = self.root / 'runtime'
        (runtime / 'tools').mkdir(parents=True)
        (runtime / 'tools/payload.txt').write_text('runtime data')
        out = runtime / '.run/application'
        result = package.assemble([self.base], out, runtime=runtime)
        self.assertEqual('runtime data', (out / 'tools/payload.txt').read_text())
        self.assertEqual((self.base / 'cell.py').read_bytes(), (out / 'cells/python/shipping_cost.py').read_bytes())
        self.assertIsNone(result['packages'][0]['git_commit'])
        self.assertEqual(package.digest((self.base / 'package.json').read_bytes()), result['packages'][0]['manifest_sha256'])

    def test_unrelated_runtime_alias_keeps_existing_copy_behavior(self):
        runtime = self.root / 'runtime'
        (runtime / 'tools').mkdir(parents=True)
        assets = self.root / 'assets'
        assets.mkdir()
        (assets / 'payload.txt').write_text('aliased data')
        (runtime / 'tools/linked').symlink_to(assets, target_is_directory=True)
        out = self.root / 'application'
        package.assemble([self.base], out, runtime=runtime)
        self.assertEqual('aliased data', (out / 'tools/linked/payload.txt').read_text())
        self.assertFalse((out / 'tools/linked').is_symlink())

    def test_existing_destination_is_never_replaced_or_removed(self):
        runtime = self.root / 'runtime'
        (runtime / 'tools/application').mkdir(parents=True)
        out = runtime / 'tools/application'
        (out / 'existing.txt').write_text('preserve existing output')
        with self.assertRaisesRegex(ValueError, 'destination must be new'):
            package.assemble([self.base], out, runtime=runtime)
        self.assertEqual('preserve existing output', (out / 'existing.txt').read_text())
        self.assertEqual(['application'], sorted(p.name for p in (runtime / 'tools').iterdir()))

    def test_warm_generated_bindings_cannot_contain_assembly_output(self):
        runtime = self.root / 'runtime'
        source = runtime / 'gen/python/polycell'
        source.mkdir(parents=True)
        (source / 'binding.py').write_text('generated_binding = True\n')
        self.reject(runtime, source / 'application', warm=True)
        self.assertEqual(['binding.py'], sorted(p.name for p in source.iterdir()))

    def test_warm_copy_keeps_nested_dependencies_and_generated_bindings(self):
        runtime = self.root / 'runtime'
        files = {'hosts/ts/node_modules/outer/node_modules/inner/index.js': 'nested dependency',
                 'hosts/rust/target/release/host': 'compiled host',
                 'gen/python/polycell/binding.py': 'generated binding'}
        for relative, value in files.items():
            path = runtime / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        out = self.root / 'application'
        package.assemble([self.base], out, runtime=runtime, warm=True)
        for relative, value in files.items():
            with self.subTest(file=relative):
                self.assertEqual(value, (out / relative).read_text())


if __name__ == '__main__':
    unittest.main()
