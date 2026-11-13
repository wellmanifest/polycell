"""Parallel contract majors keep independent implementations and behavior data."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from standard.conformance import run
from tools.polycell import package


class ParallelMajorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'baseline'
        package.export('shipping.cost', self.base)
        self.app = self.root / 'source-app'
        package.assemble([self.base], self.app, generate=True)
        self.v1 = yaml.safe_load((self.app / 'contracts/cells/shipping.cost.cell.yaml').read_text())
        self.v1_source = (self.app / 'cells/python/shipping_cost.py').read_bytes()
        self.v1_schemas = [(self.app / f'gen/jsonschema/shipping.cost.{kind}.json').read_bytes()
                           for kind in ('input', 'output')]
        self.v2 = deepcopy(self.v1)
        self.v2.update(urn=self.v1['urn'].rsplit(':', 1)[0] + ':v2', version='2.0.0',
                       input={'mass_kg': 'double', 'country': 'string'},
                       output={'fee': 'double', 'currency': 'string'},
                       examples=[{'name': 'new_interface', 'input': {'mass_kg': 1, 'country': 'PL'},
                                  'output': {'fee': 11.0, 'currency': 'PLN'}}])
        (self.app / 'contracts/cells/shipping.cost.v2.cell.yaml').write_text(yaml.safe_dump(self.v2))
        golden = {'input': {'mass_kg': 2, 'country': 'PL'}, 'output': {'fee': 12.0, 'currency': 'PLN'}}
        (self.app / 'tests/golden/shipping.cost.v2.jsonl').write_text(json.dumps(golden) + '\n')
        self.generate()
        # Regenerate the entire new implementation from its own contract/types/cases.
        code = (f"# polycell: urn={self.v2['urn']} contract={package.interface_hash(self.v2)}\n"
                'from polycell_types import ShippingCostV2Input, ShippingCostV2Output\n\n'
                'def run(input: ShippingCostV2Input) -> ShippingCostV2Output:\n'
                '    return {"fee": 10.0 + input["mass_kg"], "currency": "PLN"}\n')
        (self.app / 'cells/python/shipping_cost_v2.py').write_text(code)
        self.generate()

    def generate(self, check=True):
        return subprocess.run([sys.executable, str(self.app / 'tools/polycell/gen.py')],
                              check=check, capture_output=True, text=True)

    def export(self, selector, out):
        result = subprocess.run([sys.executable, str(self.app / 'tools/polycell/package.py'),
                                 'export', selector, '--out', str(out)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return package.verify(out)

    def test_v1_paths_and_schemas_remain_unchanged(self):
        self.assertEqual(self.v1_source, (self.app / 'cells/python/shipping_cost.py').read_bytes())
        for kind, expected in zip(('input', 'output'), self.v1_schemas):
            self.assertEqual(expected, (self.app / f'gen/jsonschema/shipping.cost.{kind}.json').read_bytes())
        cells = json.loads((self.app / 'gen/cells.index.json').read_text())['cells']
        self.assertEqual('shipping.cost', cells[self.v1['urn']]['name'])
        self.assertEqual('shipping.cost.v2', cells[self.v2['urn']]['name'])
        self.assertEqual([], [f for f in run(self.app) if f['severity'] == 'error'])

    def test_existing_python_host_dispatches_both_versions(self):
        cases = json.loads((self.app / 'tests/generated/cases.json').read_text())
        requests = ''.join(json.dumps({'urn': c['urn'], 'input': c['input']}) + '\n' for c in cases)
        reply = subprocess.run([sys.executable, str(self.app / 'hosts/python/host.py'), '--stdio'],
                               env={**os.environ, 'POLYCELL_ROOT': str(self.app)}, input=requests,
                               check=True, text=True, capture_output=True, timeout=10)
        responses = [json.loads(line) for line in reply.stdout.splitlines()]
        self.assertEqual(len(cases), len(responses))
        for case, result in zip(cases, responses):
            self.assertTrue(result['ok'], result)
            self.assertEqual(case['output'], result['output'])

    def test_prompts_select_the_version_by_urn(self):
        for contract, alias, typename in ((self.v1, 'shipping.cost', 'ShippingCostInput'),
                                          (self.v2, 'shipping.cost.v2', 'ShippingCostV2Input')):
            prompt = subprocess.check_output([sys.executable, str(self.app / 'tools/polycell/prompt.py'),
                                              contract['urn']], text=True)
            self.assertIn(contract['urn'], prompt)
            self.assertIn(typename, prompt)
            self.assertIn(alias.replace('.', '_') + '.py', prompt)

    def test_export_by_alias_or_urn_preserves_canonical_identity(self):
        for index, selector in enumerate(('shipping.cost', 'shipping.cost.v2', self.v1['urn'], self.v2['urn'])):
            manifest = self.export(selector, self.root / f'package-{index}')
            self.assertEqual('shipping.cost', manifest['name'])
            self.assertEqual(self.v1['urn'] if index in (0, 2) else self.v2['urn'], manifest['urn'])

    def test_git_bundle_roundtrip_and_joint_assembly_preserve_cases(self):
        packages = []
        for major, contract in enumerate((self.v1, self.v2), 1):
            source, bundle, clone = (self.root / f'{name}-{major}' for name in ('package', 'bundle', 'clone'))
            self.export(contract['urn'], source)
            package.git_snapshot(source, bundle)
            subprocess.run(['git', 'clone', '--quiet', str(bundle), str(clone)], check=True)
            packages.append(clone)
        assembled = self.root / 'roundtrip-app'
        package.assemble(packages, assembled, generate=True)
        original = json.loads((self.app / 'tests/generated/cases.json').read_text())
        restored = json.loads((assembled / 'tests/generated/cases.json').read_text())
        self.assertEqual(original, restored)
        self.assertTrue((assembled / 'cells/python/shipping_cost.py').is_file())
        self.assertTrue((assembled / 'cells/python/shipping_cost_v2.py').is_file())

    def test_v2_only_app_does_not_reassign_the_v1_alias(self):
        (self.app / 'contracts/cells/shipping.cost.cell.yaml').unlink()
        (self.app / 'cells/python/shipping_cost.py').unlink()
        (self.app / 'tests/golden/shipping.cost.jsonl').unlink()
        self.generate()
        cells = json.loads((self.app / 'gen/cells.index.json').read_text())['cells']
        self.assertEqual({self.v2['urn']}, set(cells))
        self.assertEqual('shipping.cost.v2', cells[self.v2['urn']]['name'])
        self.export(self.v2['urn'], self.root / 'only-v2')
        destination = self.root / 'unknown-v1'
        result = subprocess.run([sys.executable, str(self.app / 'tools/polycell/package.py'),
                                 'export', 'shipping.cost', '--out', str(destination)], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('unknown cell', result.stderr)
        self.assertFalse(destination.exists())

    def test_version_alias_collision_fails_before_overwriting_artifacts(self):
        before = {str(p.relative_to(self.app)): p.read_bytes()
                  for d in ('gen', 'tests/generated') for p in (self.app / d).rglob('*') if p.is_file()}
        conflicting = deepcopy(self.v2)
        conflicting.update(name='shipping.cost.v2', urn='urn:wm:cell:shop:shipping.cost.v2:v1', version='1.0.0')
        (self.app / 'contracts/cells/conflict.cell.yaml').write_text(yaml.safe_dump(conflicting))
        result = self.generate(check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('duplicate', result.stderr)
        after = {str(p.relative_to(self.app)): p.read_bytes()
                 for d in ('gen', 'tests/generated') for p in (self.app / d).rglob('*') if p.is_file()}
        self.assertEqual(before, after)
