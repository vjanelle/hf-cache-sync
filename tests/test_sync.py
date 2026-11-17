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
