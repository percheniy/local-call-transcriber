from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from call_transcriber.picker import mounted_folder, choose_folder
from call_transcriber.resources import plan, Resources
from call_transcriber.runtime import GIB
from call_transcriber.batch import discover


class SelectionTests(unittest.TestCase):
    def test_manual_limit_and_memory_safety(self):
        resources = Resources(64*GIB, 50*GIB, 10, 95, 0)
        self.assertEqual(plan(resources, 20)['parallel'], 1)
        for count in range(1, 6):
            self.assertEqual(plan(resources, 20, parallel=count)['parallel'], count)
        resources.available = 12*GIB
        self.assertEqual(plan(resources, 20, parallel=5)['parallel'], 0)
        for invalid in [0, 6, True, '5', None]:
            with self.assertRaises(ValueError):
                plan(resources, 20, parallel=invalid)

    def test_empty_folder_rejected(self):
        with self.assertRaises(ValueError):
            discover('')

    def test_mounted_selection_and_symlink_boundary(self):
        nonce = 'a'*32
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            directory = Path(root)/'nested'; directory.mkdir()
            marker = '.call-transcriber-selection-'+nonce
            (directory/marker).write_text(nonce)
            self.assertEqual(mounted_folder(nonce, root), str(directory.resolve()))
            (directory/marker).unlink()
            (Path(outside)/marker).write_text(nonce)
            (Path(root)/'link').symlink_to(outside)
            with self.assertRaises(ValueError):
                mounted_folder(nonce, root)

    @patch('call_transcriber.picker.sys.platform', 'darwin')
    @patch('call_transcriber.picker.subprocess.run')
    def test_native_cancel_is_empty_selection(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = '\n'
        self.assertIsNone(choose_folder())
        self.assertEqual(run.call_args.args[0][0], 'osascript')
