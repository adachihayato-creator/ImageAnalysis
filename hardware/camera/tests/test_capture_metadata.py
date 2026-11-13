import ast
from datetime import datetime
import importlib.util
import json
import os
import time
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


CAMERA_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_metadata", CAMERA_DIR / "capture_metadata.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MetadataTests(unittest.TestCase):
    def test_round_trip_missing_values_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "photo.jpg"
            metadata = {"ExposureTime": 8310, "ColourGains": (1.2, 1.8)}
            kwargs = dict(captured_at="2026-11-05T12:00:00+09:00",
                          capture_size=(2304, 1296), camera_properties={},
                          software_versions={})
            path = module.save_request_metadata(image, metadata, **kwargs)
            record = json.loads(path.read_text())
            self.assertEqual(record["metadata"]["ExposureTime"], 8310)
            self.assertEqual(record["settings"]["ColourGains"], [1.2, 1.8])
            self.assertIsNone(record["settings"]["LensPosition"])
            self.assertIn("LensPosition", record["missing_settings"])
            self.assertFalse(record["fixed_settings_verified"])
            with self.assertRaises(FileExistsError):
                module.save_request_metadata(image, metadata, **kwargs)

    def test_failed_write_does_not_leave_partial_json(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "photo.jpg"
            with patch.object(module.json, "dump", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    module.save_request_metadata(image, {}, captured_at="test",
                                                 capture_size=(1, 1),
                                                 camera_properties={}, software_versions={})
            self.assertEqual(list(Path(folder).iterdir()), [])


class CaptureTests(unittest.TestCase):
    def setUp(self):
        # Compile the real capture method without importing Pi/Tk dependencies.
        tree = ast.parse((CAMERA_DIR / "camera_app.py").read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "CameraApp")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == "capture")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.save = Mock(wraps=module.save_request_metadata)
        namespace = dict(datetime=datetime, os=os, SAVE_DIR=self.folder.name,
                         CAPTURE_SIZE=(2304, 1296), MAIN="blue", SUBTEXT="gray",
                         RED="red", save_request_metadata=self.save, time=time)
        namespace['guide_record']=lambda guide,registered:{'state':'registered' if registered else 'none',
                                                          'alignment_verified':False}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "camera_app.py", "exec"), namespace)
        self.capture = namespace["capture"]
        self.request = Mock()
        self.request.get_metadata.return_value = {"ExposureTime": 8310}
        self.request.save.side_effect = lambda stream, path: Path(path).write_bytes(b"mock JPEG")
        self.lock = Mock()
        self.lock.can_capture = True
        self.lock.capture_record.return_value = {'mode':'fixed_settings','fixed_settings_verified': True,
                                                 'frame_verification': {'passed':True}}
        self.app = SimpleNamespace(capturing=False, toast=Mock(), root=Mock(),
                                   picam2=Mock(), camera_properties={}, software_versions={},
                                   lock=self.lock, refresh_status=Mock(),editing_guide=False,
                                   guide=None,guide_registered=False)
        self.app.picam2.capture_request.return_value = self.request

    def test_same_request_for_image_and_metadata_and_release(self):
        self.capture(self.app)
        self.app.picam2.capture_request.assert_called_once_with()
        self.request.get_metadata.assert_called_once_with()
        self.request.release.assert_called_once_with()
        images = list(Path(self.folder.name).glob("*.jpg"))
        self.assertEqual(len(images), 1)
        record = json.loads(images[0].with_suffix(".json").read_text())
        self.assertEqual(record["image_filename"], images[0].name)
        self.assertEqual(record["metadata"], {"ExposureTime": 8310})
        self.assertTrue(record['fixed_settings_verified'])
        self.lock.capture_record.assert_called_once()
        self.assertFalse(self.app.capturing)

    def test_unverified_startup_blocks_capture(self):
        self.lock.can_capture = False
        self.capture(self.app)
        self.app.picam2.capture_request.assert_not_called()

    def test_frame_drift_keeps_diagnostic_pair_and_marks_failure(self):
        self.lock.capture_record.return_value = {'mode':'fixed_settings','fixed_settings_verified':False,
                                                 'frame_verification':{'passed':False,'problems':['ExposureTime']}}
        self.capture(self.app)
        sidecar=next(Path(self.folder.name).glob('*.json'))
        record=json.loads(sidecar.read_text())
        self.assertFalse(record['fixed_settings_verified'])
        self.assertIn('診断用',self.app.toast.configure.call_args.kwargs['text'])

    def test_jpeg_failure_releases_request(self):
        self.request.save.side_effect = OSError("JPEG failed")
        self.capture(self.app)
        self.request.release.assert_called_once_with()
        self.save.assert_not_called()
        self.assertFalse(self.app.capturing)

    def test_json_failure_preserves_jpeg_and_shows_partial_failure(self):
        self.save.side_effect = OSError("JSON failed")
        self.capture(self.app)
        self.assertEqual(len(list(Path(self.folder.name).glob("*.jpg"))), 1)
        self.assertIn("JPEG保存済み・JSON保存失敗",
                      self.app.toast.configure.call_args.kwargs["text"])
        self.request.release.assert_called_once_with()
        self.assertFalse(self.app.capturing)


if __name__ == "__main__":
    unittest.main()
