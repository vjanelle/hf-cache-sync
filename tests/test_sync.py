import tempfile
import unittest
from pathlib import Path

from hf_cache_sync import core


class CacheScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src, self.dst = self.root / 'src', self.root / 'dst'
        self.src.mkdir(); self.dst.mkdir()

    def model(self, root, name='models--org--model', ref='abc'):
        repo = root / name
        (repo / 'blobs').mkdir(parents=True)
        (repo / 'refs').mkdir()
        (repo / 'snapshots' / ref).mkdir(parents=True)
        (repo / 'blobs' / 'hash').write_text('weights')
        (repo / 'snapshots' / ref / 'weights').symlink_to('../../blobs/hash')
        (repo / 'refs' / 'main').write_text(ref)
        return repo

    def test_given_model_when_pulled_then_snapshot_resolves(self):
        self.model(self.src)
        core.sync(self.src, self.dst, ['org/model'])
        self.assertEqual((self.dst/'models--org--model/snapshots/abc/weights').read_text(), 'weights')
        self.assertTrue((self.dst/'models--org--model/snapshots/abc/weights').is_symlink())

    def test_given_conflicting_ref_when_syncing_then_no_changes(self):
        self.model(self.src)
        self.model(self.dst, ref='def')
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst, ['org/model'])
        self.assertFalse((self.dst/'models--org--model/snapshots/abc').exists())

    def test_given_remote_model_when_pruned_then_other_model_remains(self):
        self.model(self.dst)
        self.model(self.dst, 'models--org--other')
        core.prune(self.dst, ['org/model'])
        self.assertFalse((self.dst/'models--org--model').exists())
        self.assertTrue((self.dst/'models--org--other').exists())

    def test_given_shared_blob_when_syncing_then_target_is_copied(self):
        repo = self.model(self.src)
        (repo/'blobs/hash').unlink()
        shared = self.src/'blobs/aa/hash'
        shared.parent.mkdir(parents=True)
        shared.write_text('shared')
        (repo/'blobs/hash').symlink_to('../../blobs/aa/hash')
        core.sync(self.src, self.dst, ['org/model'])
        self.assertEqual((self.dst/'models--org--model/snapshots/abc/weights').read_text(), 'shared')

    def test_given_all_models_when_dry_run_then_nothing_written(self):
        self.model(self.src)
        self.model(self.src, 'models--org--other')
        self.assertTrue(core.sync(self.src, self.dst, dry_run=True))
        self.assertEqual(list(self.dst.iterdir()), [])

    def test_given_conflicting_ref_when_source_wins_then_ref_updated(self):
        self.model(self.src)
        self.model(self.dst, ref='def')
        core.sync(self.src, self.dst, ['org/model'], source_wins=True)
        self.assertEqual((self.dst/'models--org--model/refs/main').read_text(), 'abc')

    def test_given_incomplete_file_when_syncing_then_it_is_skipped(self):
        repo = self.model(self.src)
        (repo/'blobs/partial.incomplete').write_text('partial')
        core.sync(self.src, self.dst, ['org/model'])
        self.assertFalse((self.dst/'models--org--model/blobs/partial.incomplete').exists())

    def test_given_escaping_link_when_syncing_then_it_is_rejected(self):
        repo = self.model(self.src)
        (repo/'blobs/evil').symlink_to('../../../outside')
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst)

    def test_given_bad_model_when_selecting_then_it_is_rejected(self):
        for name in ('../bad', 'a/b/c', 'a--b/c'):
            with self.subTest(name=name), self.assertRaises(core.SyncError): core.repo_name(name)

    def test_given_prune_dry_run_then_model_remains(self):
        self.model(self.dst)
        self.assertEqual(core.prune(self.dst, ['org/model'], dry_run=True), ['models--org--model'])
        self.assertTrue((self.dst/'models--org--model').exists())

    def test_given_missing_model_or_cache_then_operation_fails(self):
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst, ['org/missing'])
        with self.assertRaises(core.SyncError): core.prune(self.dst, [])
        with self.assertRaises(core.SyncError): core.select(self.root/'missing', [])
        with self.assertRaises(core.SyncError): core.sync(self.src, self.src)

    def test_given_cli_when_pushing_and_pruning_then_it_succeeds(self):
        from hf_cache_sync.__main__ import main
        self.model(self.src)
        self.assertEqual(main(['push', '--local', str(self.src), '--remote', str(self.dst), '--all']), 0)
        self.assertEqual(main(['prune', '--remote', str(self.dst), '--model', 'org/model']), 0)

    def test_given_cli_when_model_missing_then_it_reports_failure(self):
        from hf_cache_sync.__main__ import main
        self.assertEqual(main(['pull', '--local', str(self.src), '--remote', str(self.dst), '--model', 'org/missing']), 1)

    def test_given_immutable_blob_conflict_then_it_is_rejected(self):
        self.model(self.src)
        repo = self.model(self.dst)
        (repo/'blobs/hash').write_text('different')
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst, ['org/model'])

    def test_given_absolute_link_then_it_is_rejected(self):
        repo = self.model(self.src)
        (repo/'blobs/evil').symlink_to('/etc/passwd')
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst)

    def test_given_environment_cache_paths_when_pushing_then_both_are_used(self):
        from unittest.mock import patch
        from hf_cache_sync.__main__ import main
        self.model(self.src)
        with patch.dict('os.environ', {'HF_HUB_CACHE': str(self.src), 'HF_CACHE_SYNC_REMOTE': str(self.dst)}, clear=True):
            self.assertEqual(main(['push', '--model', 'org/model']), 0)
        self.assertTrue((self.dst/'models--org--model/refs/main').exists())

    def test_given_huggingface_environment_when_resolving_local_cache_then_precedence_applies(self):
        from unittest.mock import patch
        from hf_cache_sync.__main__ import local_cache
        cases = [({'HF_HUB_CACHE': '/hub', 'HF_HOME': '/home'}, '/hub'),
                 ({'HUGGINGFACE_HUB_CACHE': '/legacy', 'HF_HOME': '/home'}, '/legacy'),
                 ({'HF_HOME': '/home'}, '/home/hub'),
                 ({'XDG_CACHE_HOME': '/xdg'}, '/xdg/huggingface/hub')]
        for env, expected in cases:
            with self.subTest(env=env), patch.dict('os.environ', env, clear=True):
                self.assertEqual(local_cache(), Path(expected))

    def test_given_no_remote_setting_when_invoked_then_it_reports_error(self):
        from unittest.mock import patch
        from hf_cache_sync.__main__ import main
        with patch.dict('os.environ', {'HF_HOME': str(self.root)}, clear=True):
            with self.assertRaises(SystemExit): main(['prune', '--model', 'org/model'])

    def test_given_large_transfer_when_verbose_then_progress_and_paths_are_reported(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from hf_cache_sync.__main__ import main
        repo = self.model(self.src)
        (repo/'blobs/hash').write_bytes(b'x' * (2 * 1024 * 1024))
        output = StringIO()
        with redirect_stderr(output):
            self.assertEqual(main(['push', '--local', str(self.src), '--remote', str(self.dst), '--all', '--verbose']), 0)
        self.assertIn(str(Path('blobs') / 'hash'), output.getvalue())
        self.assertIn('100%', output.getvalue())
        self.assertIn('MiB/s', output.getvalue())

    def test_given_dry_run_when_verbose_then_reports_plan_without_copy(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from hf_cache_sync.__main__ import main
        self.model(self.src)
        output = StringIO()
        with redirect_stderr(output):
            self.assertEqual(main(['push', '--local', str(self.src), '--remote', str(self.dst), '--all', '--dry-run', '-v']), 0)
        self.assertIn('planned', output.getvalue())
        self.assertEqual(list(self.dst.iterdir()), [])

    def test_given_kernel_copy_unsupported_after_partial_transfer_when_copying_then_fallback_resumes(self):
        import errno
        import os
        from unittest.mock import patch
        repo = self.model(self.src)
        data = b'weights' * 1000
        (repo/'blobs/hash').write_bytes(data)
        calls = []
        def partial_then_unsupported(src, dst, count):
            if not calls:
                calls.append(True)
                return os.write(dst, os.read(src, 123))
            raise OSError(errno.EXDEV, 'cross-device copy')
        with patch.object(core.os, 'copy_file_range', partial_then_unsupported, create=True):
            core.sync(self.src, self.dst, ['org/model'])
        self.assertEqual((self.dst/'models--org--model/blobs/hash').read_bytes(), data)

    def test_given_kernel_copy_io_error_when_copying_then_it_fails_without_publishing(self):
        import errno
        from unittest.mock import patch
        self.model(self.src)
        with patch.object(core.os, 'copy_file_range', side_effect=OSError(errno.EIO, 'I/O error'), create=True):
            with self.assertRaises(OSError):
                core.sync(self.src, self.dst, ['org/model'])
        self.assertFalse((self.dst/'models--org--model/blobs/hash').exists())

    def test_given_equal_size_cached_blobs_when_syncing_then_existing_blob_is_reused(self):
        self.model(self.src)
        dest = self.model(self.dst)
        (dest/'blobs/hash').write_text('WEIGHTS')
        core.sync(self.src, self.dst, ['org/model'])
        self.assertEqual((dest/'blobs/hash').read_text(), 'WEIGHTS')

    def test_given_different_size_blob_when_syncing_then_conflict_is_reported(self):
        self.model(self.src)
        dest = self.model(self.dst)
        (dest/'blobs/hash').write_text('different size')
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst, ['org/model'])

    def test_given_refs_with_same_length_but_different_values_then_conflict_is_reported(self):
        self.model(self.src, ref='abc')
        self.model(self.dst, ref='def')
        with self.assertRaises(core.SyncError): core.sync(self.src, self.dst, ['org/model'])

    def test_given_corrupt_same_size_blob_when_repairing_then_source_restores_it(self):
        self.model(self.src)
        dest = self.model(self.dst)
        (dest/'blobs/hash').write_text('WEIGHTS')
        core.sync(self.src, self.dst, ['org/model'], repair=True)
        self.assertEqual((dest/'blobs/hash').read_text(), 'weights')

    def test_given_corrupt_blob_when_repair_is_dry_run_then_it_is_unchanged(self):
        self.model(self.src)
        dest = self.model(self.dst)
        (dest/'blobs/hash').write_text('bad')
        changes = core.sync(self.src, self.dst, ['org/model'], dry_run=True, repair=True)
        self.assertIn(str(Path('models--org--model') / 'blobs' / 'hash'), changes)
        self.assertEqual((dest/'blobs/hash').read_text(), 'bad')

    def test_given_cli_repair_when_remote_is_source_then_local_is_repaired(self):
        from hf_cache_sync.__main__ import main
        self.model(self.dst)
        dest = self.model(self.src)
        (dest/'blobs/hash').write_text('bad')
        self.assertEqual(main(['repair', '--from', 'remote', '--local', str(self.src), '--remote', str(self.dst), '--model', 'org/model']), 0)
        self.assertEqual((dest/'blobs/hash').read_text(), 'weights')

    def test_given_copy_when_transferring_then_advisory_hints_do_not_change_data(self):
        from unittest.mock import patch
        from hf_cache_sync.__main__ import main
        self.model(self.src)
        with patch.object(core.os, 'posix_fadvise', create=True) as advise, \
             patch.object(core.os, 'POSIX_FADV_SEQUENTIAL', 2, create=True), \
             patch.object(core.os, 'POSIX_FADV_DONTNEED', 4, create=True):
            self.assertEqual(main(['push', '--local', str(self.src), '--remote', str(self.dst), '--all']), 0)
        self.assertTrue(any(call.args[3] == 4 for call in advise.call_args_list))
        self.assertEqual((self.dst/'models--org--model/blobs/hash').read_text(), 'weights')

    def test_given_unsupported_cache_advice_when_copying_then_transfer_succeeds(self):
        from unittest.mock import patch
        self.model(self.src)
        with patch.object(core.os, 'posix_fadvise', side_effect=OSError('unsupported'), create=True), \
             patch.object(core.os, 'POSIX_FADV_SEQUENTIAL', 2, create=True), \
             patch.object(core.os, 'POSIX_FADV_DONTNEED', 4, create=True):
            core.sync(self.src, self.dst, ['org/model'])
        self.assertEqual((self.dst/'models--org--model/blobs/hash').read_text(), 'weights')
