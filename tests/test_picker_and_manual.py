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

class CancellationTests(unittest.TestCase):
    def test_cancel_reaps_worker_and_removes_owned_partial(self):
        import subprocess
        import sys
        import time
        from call_transcriber.batch import Batch
        real_popen = subprocess.Popen
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'call.wav').touch()
            script = root/'slow.py'
            script.write_text('import sys,time,subprocess\nfrom pathlib import Path\nchild=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\np=Path(sys.argv[1]);p.parent.mkdir(exist_ok=True);p.write_text(str(child.pid))\ntime.sleep(60)\n')
            spawned = []
            def spawn(command, **kwargs):
                child = real_popen([sys.executable, str(script), command[-1]], **kwargs)
                spawned.append(child)
                return child
            with patch('call_transcriber.batch.snapshot', side_effect=lambda *a: Resources(64*GIB,50*GIB,16,0,0)), patch('call_transcriber.batch.ensure_models', return_value=root), patch('call_transcriber.batch.audio_duration', return_value=1), patch('call_transcriber.batch.subprocess.Popen', side_effect=spawn):
                batch=Batch(); batch.start(root, 2)
                deadline=time.monotonic()+5
                while not list(root.rglob('*.part')) and time.monotonic()<deadline:
                    time.sleep(.02)
                self.assertTrue(list(root.rglob('*.part')))
                import psutil
                child_pid=int(next(root.rglob('*.part')).read_text())
                batch.cancel(); batch.thread.join(10)
                try:
                    self.assertEqual(psutil.Process(child_pid).status(), psutil.STATUS_ZOMBIE)
                except psutil.NoSuchProcess:
                    pass
                self.assertFalse(batch.thread.is_alive())
                self.assertTrue(all(child.poll() is not None for child in spawned))
                self.assertFalse(list(root.rglob('*.part')))
                self.assertEqual(batch.view()['phase'], 'cancelled')
