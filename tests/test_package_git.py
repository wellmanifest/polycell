"""An assembled source and its lock must describe one immutable package."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.polycell import package


class AssemblyGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'package with spaces'
        self.meta = package.export('shipping.cost', self.base)
        self.runtime = self.root / 'empty-runtime'
        self.runtime.mkdir()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.base), *args], stderr=subprocess.STDOUT)

    def replace_source(self, marker='replacement'):
        source = (self.base / 'cell.py').read_bytes() + ('\n# ' + marker + '\n').encode()
        (self.base / 'cell.py').write_bytes(source)
        meta = json.loads((self.base / 'package.json').read_text())
        meta['files']['cell.py'] = package.digest(source)
        (self.base / 'package.json').write_bytes(package.json_bytes(meta))
        package.verify(self.base)

    def commit_replacement(self):
        self.replace_source('concurrent complete replacement')
        self.git('add', '--', 'cell.py', 'package.json')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                 '-c', 'commit.gpgSign=false', 'commit', '-m', 'Replace complete source')

    def assemble(self, name='app', **options):
        return package.assemble([self.base], self.root / name, runtime=self.runtime, **options)

    def test_index_flags_cannot_hide_content_mismatches(self):
        for flag in ('--assume-unchanged', '--skip-worktree'):
            with self.subTest(flag=flag):
                self.base = self.root / flag[2:]
                package.export('shipping.cost', self.base)
                commit = package.git_snapshot(self.base)
                self.git('update-index', flag, 'cell.py', 'package.json')
                good = self.assemble(flag[2:] + '-valid')
                self.assertEqual(commit, good['packages'][0]['git_commit'])
                self.replace_source()
                self.assertEqual(b'', self.git('status', '--porcelain'))
                with self.assertRaisesRegex(ValueError, 'Git package'):
                    self.assemble(flag[2:] + '-invalid')
                self.assertFalse((self.root / (flag[2:] + '-invalid')).exists())

    def test_missing_committed_artifact_is_rejected_even_if_status_hides_untracked_files(self):
        package.git_snapshot(self.base)
        self.git('rm', '--cached', '--', 'README.md')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                 '-c', 'commit.gpgSign=false', 'commit', '-m', 'Omit artifact from tree')
        self.git('config', 'status.showUntrackedFiles', 'no')
        self.assertEqual(b'', self.git('status', '--porcelain'))
        package.verify(self.base)
        with self.assertRaisesRegex(ValueError, 'Git package'):
            self.assemble()
        self.assertFalse((self.root / 'app').exists())

    def test_extra_committed_source_cannot_hide_in_skip_worktree_entries(self):
        package.git_snapshot(self.base)
        (self.base / 'helper.py').write_text('value = 1\n')
        self.git('add', '--force', '--', 'helper.py')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                 '-c', 'commit.gpgSign=false', 'commit', '-m', 'Add extra source')
        self.git('update-index', '--skip-worktree', 'helper.py')
        (self.base / 'helper.py').unlink()
        self.assertEqual(b'', self.git('status', '--porcelain'))
        package.verify(self.base)
        with self.assertRaisesRegex(ValueError, 'Git package'):
            self.assemble()
        self.assertFalse((self.root / 'app').exists())

    def test_source_commit_during_copy_cannot_relabel_already_copied_bytes(self):
        commit = package.git_snapshot(self.base)
        manifest = (self.base / 'package.json').read_bytes()
        original = (self.base / 'cell.py').read_bytes()
        copyfile = shutil.copyfile
        edits = []
        def copy(source, target, *args, **options):
            result = copyfile(source, target, *args, **options)
            if Path(target).as_posix().endswith('/cells/python/shipping_cost.py'):
                edits.append(True)
                self.commit_replacement()
            return result
        with patch.object(package.shutil, 'copyfile', side_effect=copy):
            result = self.assemble()
        self.assertEqual([True], edits)
        self.assertNotEqual(commit, self.git('rev-parse', 'HEAD').decode().strip())
        self.assertEqual(b'', self.git('status', '--porcelain'))
        self.assertEqual(original, (self.root / 'app/cells/python/shipping_cost.py').read_bytes())
        self.assertEqual(commit, result['packages'][0]['git_commit'])
        self.assertEqual(package.digest(manifest), result['packages'][0]['manifest_sha256'])
        self.assertEqual(result, json.loads((self.root / 'app/cellset.lock.json').read_text()))

    def test_record_git_false_accepts_verified_uncommitted_bytes_without_git_queries(self):
        package.git_snapshot(self.base)
        self.replace_source()
        manifest = (self.base / 'package.json').read_bytes()
        with patch.object(package.subprocess, 'check_output', side_effect=AssertionError('unexpected Git query')):
            result = self.assemble(record_git=False)
        self.assertIsNone(result['packages'][0]['git_commit'])
        self.assertEqual(package.digest(manifest), result['packages'][0]['manifest_sha256'])
        self.assertEqual((self.base / 'cell.py').read_bytes(),
                         (self.root / 'app/cells/python/shipping_cost.py').read_bytes())

    def test_sha256_git_repositories_keep_their_exact_commit(self):
        with patch.dict(os.environ, {'GIT_DEFAULT_HASH': 'sha256'}):
            commit = package.git_snapshot(self.base)
        self.assertEqual(64, len(commit))
        result = self.assemble()
        self.assertEqual(commit, result['packages'][0]['git_commit'])
        self.assertEqual((self.base / 'cell.py').read_bytes(),
                         (self.root / 'app/cells/python/shipping_cost.py').read_bytes())

    def test_clean_filters_cannot_substitute_normalized_committed_bytes(self):
        source = (self.base / 'cell.py').read_bytes().replace(b'\n', b'\r\n')
        (self.base / 'cell.py').write_bytes(source)
        self.meta['files']['cell.py'] = package.digest(source)
        (self.base / 'package.json').write_bytes(package.json_bytes(self.meta))
        with patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.autocrlf',
                                     'GIT_CONFIG_VALUE_0': 'true'}):
            commit = package.git_snapshot(self.base)
            self.assertEqual(b'', self.git('status', '--porcelain'))
            self.assertNotEqual(source, self.git('show', commit + ':cell.py'))
            with self.assertRaisesRegex(ValueError, 'Git package'):
                self.assemble()
        self.assertFalse((self.root / 'app').exists())

    def test_committed_symlink_cannot_describe_a_regular_working_artifact(self):
        (self.base / 'README.md').write_text('artifact-target')
        self.meta['files']['README.md'] = package.digest(b'artifact-target')
        (self.base / 'package.json').write_bytes(package.json_bytes(self.meta))
        commit = package.git_snapshot(self.base)
        blob = self.git('rev-parse', commit + ':README.md').decode().strip()
        self.git('update-index', '--cacheinfo', '120000,' + blob + ',README.md')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                 '-c', 'commit.gpgSign=false', 'commit', '-m', 'Change committed artifact mode')
        self.git('update-index', '--skip-worktree', 'README.md')
        self.assertEqual(b'', self.git('status', '--porcelain'))
        package.verify(self.base)
        with self.assertRaisesRegex(ValueError, 'Git package'):
            self.assemble()
        self.assertFalse((self.root / 'app').exists())

    def test_output_cannot_invalidate_its_own_source_package(self):
        before = {p.name: p.read_bytes() for p in self.base.iterdir()}
        for out in (self.base, self.base / 'application'):
            with self.subTest(out=out), self.assertRaisesRegex(ValueError, 'outside source packages'):
                package.assemble([self.base], out, runtime=self.runtime)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.base.iterdir()})
        package.verify(self.base)


if __name__ == '__main__':
    unittest.main()
