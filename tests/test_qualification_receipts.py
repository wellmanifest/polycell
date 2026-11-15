"""Worker success must describe the exact qualification before publication."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.polycell import forge, package


def invalid_receipts(valid):
    """Wire faults used by public qualification and the private Docker audit."""
    faults = [('empty', b''), ('malformed', b'worker finished\n{'),
              ('null', b'null\n'), ('array', b'[]\n'), ('scalar', b'7\n'),
              ('invalid-utf8', json.dumps({**valid, 'note': 'MARKER'}).encode().replace(b'MARKER', b'\xff')),
              ('duplicate-key', (json.dumps(valid)[:-1] + ', "ok": true}\n').encode()),
              ('float-overflow', json.dumps({**valid, 'note': 'OVERFLOW'}).encode().replace(b'"OVERFLOW"', b'1e400'))]
    for key in valid:
        faults.append(('missing-' + key, json.dumps({k: v for k, v in valid.items() if k != key}).encode()))
    changes = {
        'ok': [False, 0, 1, 'true', 'false', None, [], {'success': True}],
        'schema': ['other/v1', None], 'urn': ['urn:wm:cell:other:wrong:v1', None],
        'owner': ['unsupported', None], 'transport': ['http', None], 'network': ['host', None],
        'cases': [0, -1, True, float(valid['cases']), '1', None, valid['cases'] + 1],
        'build_s': [-1, True, '0', None, float('nan'), float('inf'), -float('inf')],
        'elapsed_s': [-1, True, '0', None, float('nan'), float('inf'), -float('inf')],
        'extra': [{'nested': float('nan')}],
    }
    for key, values in changes.items():
        for number, value in enumerate(values):
            faults.append((f'{key}-{number}', json.dumps({**valid, key: value}).encode()))
    return faults


class QualificationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'baseline'
        self.meta = package.export('shipping.cost', self.base)
        self.image = 'sha256:' + '1' * 64
        self.valid = {'schema': 'wellmanifest.polycell.qualification/v1', 'ok': True,
                      'urn': self.meta['urn'], 'owner': self.meta['owner'],
                      'cases': len(json.loads((self.base / 'cases.json').read_text())),
                      'transport': 'stdio', 'network': 'none', 'build_s': 0, 'elapsed_s': 1.5}

    @contextmanager
    def worker(self, replies, returncode=0, timeout=False):
        replies = iter(replies)
        commands = []
        def run(command, **options):
            commands.append(command)
            if command[1] == 'run':
                if timeout:
                    raise subprocess.TimeoutExpired(command, options['timeout'])
                options['stdout'].write(next(replies))
                return subprocess.CompletedProcess(command, returncode)
            return subprocess.CompletedProcess(command, 0)
        with patch.object(package.subprocess, 'check_output', return_value=self.image + '\n'), \
             patch.object(package.subprocess, 'run', side_effect=run):
            yield commands

    def qualify(self):
        return package.qualify(self.base, self.base, 'worker-image')

    def test_valid_receipt_preserves_metadata_and_binds_local_snapshots(self):
        receipt = {**self.valid, 'note': {'diagnostic': 'preserved'},
                   'candidate_sha256': 'untrusted', 'oracle_sha256': 'untrusted', 'image': 'untrusted'}
        with self.worker([b'build output\n' + json.dumps(receipt).encode() + b'\n']) as commands:
            result = self.qualify()
        self.assertEqual({key: result[key] for key in self.valid}, self.valid)
        self.assertEqual(receipt['note'], result['note'])
        expected = package.digest((self.base / 'package.json').read_bytes())
        self.assertEqual(expected, result['candidate_sha256'])
        self.assertEqual(expected, result['oracle_sha256'])
        self.assertEqual(self.image, result['image'])
        self.assertEqual(['docker', 'rm', '-f'], commands[-1][:3])

    def reject_faults(self, select):
        for name, raw in invalid_receipts(self.valid):
            if select(name):
                with self.subTest(fault=name), self.worker([raw]) as commands:
                    with self.assertRaisesRegex(ValueError, 'invalid qualification receipt'):
                        self.qualify()
                    self.assertEqual(['docker', 'rm', '-f'], commands[-1][:3])

    def test_invalid_json_and_encoding_have_qualification_diagnostics(self):
        self.reject_faults(lambda name: name in {'empty', 'malformed', 'null', 'array', 'scalar',
                                                'invalid-utf8', 'duplicate-key', 'float-overflow', 'extra-0'})

    def test_every_worker_receipt_field_is_required(self):
        self.reject_faults(lambda name: name.startswith('missing-'))

    def test_identity_and_execution_metadata_match_qualified_package(self):
        self.reject_faults(lambda name: name.split('-')[0] in {'schema', 'urn', 'owner', 'transport', 'network'})
        with self.worker([json.dumps({**self.valid, 'owner': 'rust'}).encode()]):
            with self.assertRaisesRegex(ValueError, 'invalid qualification receipt'):
                self.qualify()

    def test_success_is_literal_true_and_case_count_is_exact_integer(self):
        self.reject_faults(lambda name: name.startswith(('ok-', 'cases-')))

    def test_timing_metadata_is_finite_nonnegative_number(self):
        self.reject_faults(lambda name: name.startswith(('build_s-', 'elapsed_s-')))

    def test_nonzero_worker_status_cannot_be_overridden_by_success_json(self):
        with self.worker([json.dumps(self.valid).encode()], returncode=1) as commands:
            with self.assertRaisesRegex(ValueError, 'qualification failed'):
                self.qualify()
        self.assertEqual(['docker', 'rm', '-f'], commands[-1][:3])

    def test_timeout_still_cleans_up_worker(self):
        with self.worker([], timeout=True) as commands:
            with self.assertRaisesRegex(ValueError, 'qualification deadline exceeded'):
                self.qualify()
        self.assertEqual(['docker', 'rm', '-f'], commands[-1][:3])

    def regenerate(self, receipts):
        prompts = []
        def propose(baseline, candidate, audit, model, url, objective, timeout, reasoning):
            prompts.append(objective)
            package.replace(baseline, (baseline / 'cell.py').read_text(), candidate)
        out, audit = self.root / 'published', self.root / 'audit'
        with patch.object(forge, 'propose', side_effect=propose), self.worker(receipts):
            result = forge.regenerate(self.base, out, audit, 'fixture', 'http://localhost',
                                      'Regenerate the complete file', self.base, 'worker-image', attempts=2)
        return result, prompts

    def test_regeneration_retains_invalid_receipt_feedback_before_valid_qualification(self):
        bad = json.dumps({**self.valid, 'ok': 'false'}).encode()
        result, prompts = self.regenerate([bad, json.dumps(self.valid).encode()])
        self.assertEqual(2, result['attempts'])
        report = json.loads((self.root / 'audit/report.json').read_text())
        self.assertEqual('qualification', report['attempts'][0]['stage'])
        self.assertIn('invalid qualification receipt', report['attempts'][0]['error'])
        self.assertIn(report['attempts'][0]['error'], prompts[1])
        self.assertEqual('accepted', report['attempts'][1]['stage'])
        self.assertTrue((self.root / 'audit/attempt-001/candidate/cell.py').exists())
        package.verify(self.root / 'published')

    def test_invalid_receipts_exhaust_budget_without_publishing(self):
        bad = json.dumps({**self.valid, 'cases': 0}).encode()
        with self.assertRaisesRegex(ValueError, 'after 2 attempts'):
            self.regenerate([bad, bad])
        self.assertFalse((self.root / 'published').exists())
        report = json.loads((self.root / 'audit/report.json').read_text())
        self.assertFalse(report['ok'])
        self.assertEqual(2, len(report['attempts']))
        self.assertTrue(all('invalid qualification receipt' in entry['error'] for entry in report['attempts']))


if __name__ == '__main__':
    unittest.main()
