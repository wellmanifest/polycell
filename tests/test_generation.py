"""Composition regressions against real isolated application directories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from tools.polycell import package
from tools.polycell.model import load_cells


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'package'
        package.export('shipping.cost', self.base)
        self.app = self.root / 'app'
        package.assemble([self.base], self.app)
        self.generate()

    def generate(self, check=True):
        return subprocess.run([sys.executable, str(self.app / 'tools/polycell/gen.py')],
                              check=check, text=True, capture_output=True)

    def artifacts(self):
        return {str(path.relative_to(self.app)): path.read_bytes()
                for directory in ('gen', 'tests/generated') for path in (self.app / directory).rglob('*') if path.is_file()}

    def test_single_cell_app_runs_its_own_tests(self):
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                cwd=self.app, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('Ran 3 tests', result.stderr)
        self.assertFalse((self.app / 'tests/test_packages.py').exists())
        self.assertFalse((self.app / 'twin/scenarios/ui-checkout.cdp.tql').exists())
        self.assertTrue((self.app / 'tests/generated/shipping.cost.cdp.tql').is_file())

    def test_cell_path_uses_selected_application_root(self):
        self.assertEqual(self.app / 'cells/python/shipping_cost.py', load_cells(self.app)[0].cell_path)

    def test_collisions_fail_before_overwriting_artifacts(self):
        original = yaml.safe_load((self.app / 'contracts/cells/shipping.cost.cell.yaml').read_text())
        before = self.artifacts()
        pairs = [('shipping.cost', 'shipping.cost'), ('a.b_c', 'a_b.c'), ('a.b1', 'a.b_1')]
        for first, second in pairs:
            with self.subTest(names=(first, second)):
                paths = []
                for index, name in enumerate((first, second), 2):
                    contract = {**original, 'name': name, 'urn': f'urn:wm:cell:shop:{name}:v{index}'}
                    path = self.app / f'contracts/cells/collision{index}.cell.yaml'
                    path.write_text(yaml.safe_dump(contract))
                    paths.append(path)
                result = self.generate(check=False)
                self.assertNotEqual(0, result.returncode)
                self.assertIn('duplicate', result.stderr)
                self.assertEqual(before, self.artifacts())
                for path in paths:
                    path.unlink()

    def test_removed_contracts_prune_only_generated_outputs(self):
        packages = []
        for name in ('customer.validate', 'notify.render', 'pricing.quote'):
            out = self.root / name
            package.export(name, out)
            packages.append(out)
        self.app = self.root / 'checkout'
        package.assemble(packages, self.app, generate=True)
        (self.app / 'contracts/cells/notify.render.cell.yaml').unlink()
        (self.app / 'cells/ts/notify_render.ts').unlink()
        (self.app / 'contracts/processes/checkout.process.yaml').unlink()
        sentinel = self.app / 'gen/README.txt'
        sentinel.write_text('Keep unrelated artifacts')
        self.generate()
        for path in ('gen/jsonschema/notify.render.input.json', 'gen/jsonschema/notify.render.output.json',
                     'tests/generated/notify.render.testql.toon.yaml', 'tests/generated/notify.render.cdp.tql',
                     'tests/generated/process.checkout.cases.json'):
            self.assertFalse((self.app / path).exists(), path)
        self.assertTrue((self.app / 'gen/jsonschema/pricing.quote.input.json').is_file())
        self.assertEqual('Keep unrelated artifacts', sentinel.read_text())
        after = self.artifacts()
        self.generate()
        self.assertEqual(after, self.artifacts(), 'regeneration must be deterministic')

    def test_golden_only_cell_gets_browser_scenario(self):
        path = self.app / 'contracts/cells/shipping.cost.cell.yaml'
        contract = yaml.safe_load(path.read_text())
        contract['examples'] = []
        path.write_text(yaml.safe_dump(contract))
        self.generate()
        scenario = (self.app / 'tests/generated/shipping.cost.cdp.tql').read_text()
        first = json.loads((self.app / 'tests/generated/cases.json').read_text())[0]
        self.assertIn(':golden', first['name'])
        self.assertIn('CLICK [data-testid=run]', scenario)
        self.assertIn(json.dumps(str(first['input']['weight_kg'])), scenario)


if __name__ == '__main__':
    unittest.main()
