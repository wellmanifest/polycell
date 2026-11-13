"""Provider installation preserves existing paths and publishes only on success."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.polycell import setup_forge


class ProviderInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'app'
        self.forge = Path(self.temp.name) / 'forge'
        (self.root / 'integrations').mkdir(parents=True)
        self.forge.mkdir()
        (self.forge / 'provider.whl').write_bytes(b'pinned provider')
        self.lock = self.root / 'integrations/forge.lock.json'
        self.lock.write_text(json.dumps({'wheels': {
            'provider.whl': hashlib.sha256(b'pinned provider').hexdigest()}}))
        self.cache = self.root / '.subactor/cache/forge-provider'
        self.legacy = self.root / '.run/forge-provider'

    def test_cache_install_and_compatible_alias_can_be_reused(self):
        with patch.object(setup_forge.subprocess, 'run') as run:
            python = setup_forge.install(self.root, self.forge)
            self.assertEqual(self.cache / 'bin/python', python)
            self.assertEqual(str(self.cache), run.call_args_list[0].args[0][-1])
            self.assertEqual(str(python), run.call_args_list[1].args[0][0])
            self.assertEqual(str((self.forge / 'provider.whl').resolve()),
                             run.call_args_list[2].args[0][-1])
            self.assertTrue(self.legacy.is_symlink())
            self.assertEqual(self.cache, self.legacy.resolve())
            setup_forge.install(self.root, self.forge)
            self.assertEqual(6, run.call_count)

    def test_digest_failure_has_no_installation_effect(self):
        (self.forge / 'provider.whl').write_bytes(b'changed')
        with patch.object(setup_forge.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                setup_forge.install(self.root, self.forge)
        run.assert_not_called()
        self.assertFalse((self.root / '.subactor').exists())
        self.assertFalse(self.legacy.parent.exists())

    def test_old_environment_requires_explicit_migration(self):
        self.legacy.mkdir(parents=True)
        marker = self.legacy / 'keep'
        marker.write_text('existing data')
        with patch.object(setup_forge.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'migrat'):
                setup_forge.install(self.root, self.forge)
        run.assert_not_called()
        self.assertEqual('existing data', marker.read_text())
        self.assertFalse(self.cache.exists())

    def test_foreign_legacy_link_is_preserved(self):
        self.legacy.parent.mkdir()
        outside = self.forge / 'unknown-environment'
        self.legacy.symlink_to(outside, target_is_directory=True)
        with patch.object(setup_forge.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'symlink'):
                setup_forge.install(self.root, self.forge)
        run.assert_not_called()
        self.assertEqual(outside, self.legacy.readlink())
        self.assertFalse(self.cache.exists())

    def test_symlinked_cache_or_runtime_components_are_rejected(self):
        for rel in ('.subactor', '.subactor/cache',
                    '.subactor/cache/forge-provider', '.run'):
            with self.subTest(path=rel):
                target = self.root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(self.forge, target_is_directory=True)
                try:
                    with patch.object(setup_forge.subprocess, 'run') as run:
                        with self.assertRaisesRegex(ValueError, 'symlink'):
                            setup_forge.install(self.root, self.forge)
                    run.assert_not_called()
                    self.assertTrue(target.is_symlink())
                finally:
                    target.unlink()

    def test_nondirectory_cache_or_runtime_components_are_preserved(self):
        for rel in ('.subactor', '.subactor/cache',
                    '.subactor/cache/forge-provider', '.run'):
            with self.subTest(path=rel):
                target = self.root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('keep')
                try:
                    with patch.object(setup_forge.subprocess, 'run') as run:
                        with self.assertRaisesRegex(ValueError, 'directory'):
                            setup_forge.install(self.root, self.forge)
                    run.assert_not_called()
                    self.assertEqual('keep', target.read_text())
                finally:
                    target.unlink()

    def test_failed_install_does_not_publish_legacy_alias(self):
        error = subprocess.CalledProcessError(1, ['pip'])
        with patch.object(setup_forge.subprocess, 'run', side_effect=[None, error]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                setup_forge.install(self.root, self.forge)
        self.assertEqual(2, run.call_count)
        self.assertFalse(self.legacy.exists())
        self.assertFalse(self.legacy.is_symlink())
