import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from call_transcriber.batch import Batch, discover
from call_transcriber.resources import GIB, Resources, plan


class FolderTests(unittest.TestCase):
    def test_mixed_recursive_and_collision_safe_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'nested').mkdir()
            (root / 'transcription').mkdir()
            for name in ['call.mp3', 'call.WAV', 'nested/second.wav', 'transcription/ignored.mp3']:
                (root / name).touch()
            jobs = discover(root)
            self.assertEqual(len(jobs), 3)
            self.assertEqual(len({j['output'] for j in jobs}), 3)
            result = Path(jobs[0]['output'])
            result.write_text('preserve')
            self.assertEqual(discover(root)[0]['status'], 'skipped')
            self.assertEqual(result.read_text(), 'preserve')

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.wav').touch()
            (root / 'elsewhere').mkdir()
            (root / 'transcription').symlink_to(root / 'elsewhere', target_is_directory=True)
            with self.assertRaises(ValueError):
                discover(root)


class PlanningTests(unittest.TestCase):
    def test_large_computer_selects_five(self):
        result = plan(Resources(64*GIB, 50*GIB, 16, 10, 0), 20, 2*GIB)
        self.assertEqual(result['parallel'], 5)

    def test_small_computer_selects_one(self):
        result = plan(Resources(8*GIB, 5*GIB, 4, 0, 0), 20)
        self.assertEqual(result['parallel'], 1)

    def test_no_memory_and_long_recording(self):
        self.assertEqual(plan(Resources(8*GIB, 2*GIB, 4, 0, 0), 5)['parallel'], 0)
        result = plan(Resources(32*GIB, 20*GIB, 16, 0, 0), 5, duration=36000)
        self.assertEqual(result['parallel'], 1)

    def test_cpu_load_limits_parallelism(self):
        self.assertEqual(plan(Resources(64*GIB, 50*GIB, 16, 95, 0), 5)['parallel'], 1)


class SchedulerTests(unittest.TestCase):
    def test_actual_five_process_admission_and_resume(self):
        real_popen = subprocess.Popen
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i in range(7):
                (root / f'{i}.wav').touch()
            script = root / 'fake_worker.py'
            script.write_text('''import sys,time,json\nfrom pathlib import Path\ntime.sleep(1.2)\np=Path(sys.argv[1]);p.parent.mkdir(exist_ok=True);p.write_text("speaker 1: Test")\nprint('CALL_EVENT '+json.dumps(dict(event='done',warnings=[])),flush=True)\n''')
            def spawn(command, **kwargs):
                return real_popen([sys.executable, str(script), command[4]], **kwargs)
            with patch('call_transcriber.batch.snapshot', side_effect=lambda *a: Resources(64*GIB, 50*GIB, 16, 0, 0)), \
                 patch('call_transcriber.batch.ensure_models', return_value=root), \
                 patch('call_transcriber.batch.audio_duration', return_value=1), \
                 patch('call_transcriber.batch.subprocess.Popen', side_effect=spawn):
                batch = Batch()
                batch.start(root)
                max_active = 0
                deadline = time.monotonic() + 25
                while batch.thread.is_alive() and time.monotonic() < deadline:
                    max_active = max(max_active, batch.view()['active'])
                    time.sleep(.05)
                self.assertFalse(batch.thread.is_alive())
                state = batch.view()
                self.assertEqual(max_active, 5)
                self.assertTrue(all(j['status'] == 'done' for j in state['jobs']), state)
                batch.start(root)
                batch.thread.join(5)
                self.assertTrue(all(j['status'] == 'skipped' for j in batch.view()['jobs']))
                self.assertFalse(list(root.rglob('*.json')))


if __name__ == '__main__':
    unittest.main()
