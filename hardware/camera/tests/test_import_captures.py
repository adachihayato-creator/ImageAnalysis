import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import os
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('import_captures', Path(__file__).resolve().parents[1] / 'import_captures.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeTransport:
    def __init__(self):
        self.files = {'photo.jpg': b'\xff\xd8test JPEG',
                      'photo.json': json.dumps({'image_filename': 'photo.jpg'}).encode()}
        self.downloads = 0
        self.entry = {'image': 'photo.jpg', 'json': 'photo.json',
                      'sha256': [hashlib.sha256(v).hexdigest() for v in self.files.values()],
                      'sizes': [len(v) for v in self.files.values()]}

    def download(self, name, destination):
        self.downloads += 1
        destination.write_bytes(self.files[name])


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dest = Path(self.folder.name)
        self.remote = FakeTransport()

    def test_import_then_skip_without_download(self):
        self.assertTrue(module.import_pair(self.remote, self.remote.entry, self.dest))
        self.assertFalse(module.import_pair(self.remote, self.remote.entry, self.dest))
        self.assertEqual(self.remote.downloads, 2)
        self.assertEqual((self.dest / 'photo.jpg').read_bytes(), self.remote.files['photo.jpg'])

    def test_conflict_never_overwrites(self):
        (self.dest / 'photo.jpg').write_bytes(b'original')
        with self.assertRaises(FileExistsError):
            module.import_pair(self.remote, self.remote.entry, self.dest)
        self.assertEqual((self.dest / 'photo.jpg').read_bytes(), b'original')
        self.assertEqual(self.remote.downloads, 0)

    def test_interruption_and_resume_partial_pair(self):
        original = Path.hardlink_to
        def interrupted(path, source):
            if path.suffix == '.json':
                raise OSError('simulated interruption')
            original(path, source)
        with patch.object(Path, 'hardlink_to', interrupted):
            with self.assertRaises(OSError):
                module.import_pair(self.remote, self.remote.entry, self.dest)
        self.assertTrue((self.dest / 'photo.jpg').exists())
        self.assertFalse((self.dest / 'photo.json').exists())
        self.assertTrue(module.import_pair(self.remote, self.remote.entry, self.dest))
        self.assertTrue((self.dest / 'photo.json').exists())

    def test_corrupt_download_is_not_published(self):
        self.remote.files['photo.jpg'] = b'corrupted'
        with self.assertRaises(ValueError):
            module.import_pair(self.remote, self.remote.entry, self.dest)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_path_escape_rejected(self):
        self.remote.entry['image'] = '../photo.jpg'
        with self.assertRaises(ValueError):
            module.import_pair(self.remote, self.remote.entry, self.dest)

    def test_organized_pairs_are_not_restored_to_trial_folder(self):
        organized = self.dest / 'organized'
        organized.mkdir()
        trial = self.dest / 'trial'
        module.import_pair(self.remote, self.remote.entry, organized)
        self.remote.inventory = lambda: [self.remote.entry]
        self.remote.downloads = 0
        failures = module.sync_once(self.remote, trial, {'photo.jpg': organized})
        self.assertEqual(failures, 0)
        self.assertEqual(self.remote.downloads, 0)
        self.assertEqual(list(trial.iterdir()), [])

    def test_route_updates_are_read_without_restarting_watcher(self):
        config_path=self.dest/'config.json'
        route_file=self.dest/'routes.json'
        config={'routes_file':'routes.json'}
        route_file.write_text(json.dumps({'photo.jpg':'before'}))
        self.assertEqual(module.load_routes(config_path,config)['photo.jpg'],self.dest/'before')
        route_file.write_text(json.dumps({'photo.jpg':'after'}))
        self.assertEqual(module.load_routes(config_path,config)['photo.jpg'],self.dest/'after')

    def test_remote_inventory_excludes_unpaired_recent_and_invalid(self):
        for name, data in self.remote.files.items():
            p = self.dest / name
            p.write_bytes(data)
            os.utime(p, (time.time() - 10, time.time() - 10))
        (self.dest / 'orphan.jpg').write_bytes(b'test')
        (self.dest / 'recent.jpg').write_bytes(b'new')
        (self.dest / 'recent.json').write_text('{"image_filename":"recent.jpg"}')
        (self.dest / 'invalid.jpg').write_bytes(b'test')
        (self.dest / 'invalid.json').write_text('broken JSON')
        output = subprocess.check_output([sys.executable, '-c', module.REMOTE_LIST, str(self.dest)])
        self.assertEqual(json.loads(output), [self.remote.entry])


if __name__ == '__main__':
    unittest.main()
